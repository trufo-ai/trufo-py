# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""trufo-local: C2PA signing of files in listed folders, by path.

``POST /c2pa/sign`` takes the Trufo API's sign request fields, with an input and an output
path in place of the media, and signs through Trufo's distributed flow: the files stay in
their folders, and only the claim goes to Trufo. When the watermark engine is installed, the
service also watermarks. ``GET /health`` reports the image's version and the engine's, and
the watermark engine's when it is installed.
"""

import asyncio
import importlib.metadata
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import tfprov
from entrypoint import parse_folder_list
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from tfprov.c2pa_generator import cg_request
from tfprov.c2pa_generator.remote_orchestrator import generate_claim_remote
from tfprov.c2pa_generator.sb_watermark import (
    is_watermark_entry,
    require_watermark_engine,
    validate_and_strip_watermark,
)
from tfprov.c2pa_generator.trufo_actions import WatermarkApplyError
from tfprov.c2pa_py.errors import RedactionError, RemoteSignError

from trufo.api.endpoints import TRUFO_API_URL
from trufo.c2pa.manifest import SignedIngredientPolicy, SignedInputPolicy

logger = logging.getLogger(__name__)

# signs in flight at once; a request waiting for a slot holds no thread
_SIGN_SLOTS = 2


class C2PASignRequest(BaseModel):
    """The Trufo API's sign request, naming an input and an output file instead of sending media."""

    media_input_path: str
    media_output_path: str
    actions: list[Any]
    assertions: list[Any] = []
    manifest_title: str | None = None
    ingredient_title: str | None = None
    manifest_settings: dict[str, Any] | None = None
    watermark_settings: dict[str, Any] | None = None
    branded_gp_id: str | None = None
    signed_input_policy: SignedInputPolicy | None = None
    signed_ingredient_policy: SignedIngredientPolicy | None = None
    skip_manifest_storage: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Read the settings and check the watermark engine once, at start."""
    app.state.input_dirs = parse_folder_list("TRUFO_LOCAL_INPUT_DIRS", "read")
    app.state.output_dirs = parse_folder_list("TRUFO_LOCAL_OUTPUT_DIRS", "write to")
    app.state.trufo_api_url = os.environ.get("TRUFO_API_URL", TRUFO_API_URL)
    app.state.version = os.environ["TRUFO_LOCAL_VERSION"]
    app.state.watermark_engine_version = _watermark_engine_version()
    app.state.sign_slots = asyncio.BoundedSemaphore(_SIGN_SLOTS)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(Exception)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer an unexpected error as the Trufo API does, without its details."""
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/health")
async def health(request: Request) -> dict:
    """Report the versions of the image, its engine and, if installed, its watermark engine."""
    state = request.app.state
    report = {
        "status": "healthy",
        "version": state.version,
        "engine_version": tfprov.__version__,
    }
    if state.watermark_engine_version is not None:
        report["watermark_engine_version"] = state.watermark_engine_version
    return report


@app.post("/c2pa/sign", response_model=None)
async def sign(body: C2PASignRequest, request: Request) -> dict | Response:
    """Sign the input file into the output file with the caller's key."""
    api_key = request.headers.get("X-API-Key", "")
    if not api_key:
        raise HTTPException(status_code=401, detail="MissingAuthentication")
    state = request.app.state
    validation_warnings = []
    watermark_options = {}
    if body.watermark_settings is not None:
        normalize_settings = getattr(cg_request, "normalize_watermark_settings", None)
        if normalize_settings is None:
            raise HTTPException(
                status_code=400,
                detail="Watermark settings require trufo-provenance 2.3 or later.",
            )
        try:
            normalize_settings(body.watermark_settings)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        watermark_options["watermark_settings"] = body.watermark_settings
    if any(is_watermark_entry(entry) for entry in body.actions):
        if state.watermark_engine_version is None:
            raise HTTPException(status_code=400, detail="WatermarkNotAvailable")
        # only validate_and_strip_watermark's NotImplementedError is a 501; the engine
        # validates again but does not return these warnings
        try:
            _, _, validation_warnings = validate_and_strip_watermark(body.actions)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
    # in a thread, so a stalled folder mount cannot stall the server
    media_input_path, media_output_path = await asyncio.to_thread(
        _check_paths, body, state.input_dirs, state.output_dirs
    )

    async with state.sign_slots:
        # a client that left while waiting is not signed; nothing receives this response
        if await request.is_disconnected():
            return Response(status_code=499)
        try:
            written_path, warnings = await asyncio.to_thread(
                generate_claim_remote,
                api_key,
                media_input_path=media_input_path,
                media_output_path=media_output_path,
                actions=body.actions,
                assertions=body.assertions,
                trufo_api_url=state.trufo_api_url,
                manifest_title=body.manifest_title,
                ingredient_title=body.ingredient_title,
                manifest_settings=body.manifest_settings,
                **watermark_options,
                branded_gp_id=body.branded_gp_id,
                signed_input_policy=body.signed_input_policy,
                signed_ingredient_policy=body.signed_ingredient_policy,
                # only when set, so an engine without this parameter still signs
                **({"skip_manifest_storage": True} if body.skip_manifest_storage else {}),
            )
        except RemoteSignError as exc:
            # trufo's own 4xx errors pass through; any other trufo failure is upstream's
            if (
                exc.status_code is not None
                and 400 <= exc.status_code < 500
                and exc.detail is not None
            ):
                raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
            logger.warning("%s", exc)
            raise HTTPException(status_code=502, detail="TrufoAPIError") from exc
        except (RedactionError, ValueError, WatermarkApplyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            # the engine raises it for other missing files too, such as ffprobe
            if not await asyncio.to_thread(os.path.isfile, media_input_path):
                raise HTTPException(status_code=404, detail="MediaInputPathNotFound") from exc
            raise
    return {"media_output_path": written_path, "warnings": validation_warnings + warnings}


def _watermark_engine_version() -> str | None:
    """Return the watermark engine's version, or None if it is not installed.

    Raises:
        ImportError: If it is installed but cannot be imported.
    """
    try:
        version = importlib.metadata.version("trufo-pawprint")
    except importlib.metadata.PackageNotFoundError:
        return None
    # a broken install fails the start, not the first watermark request
    require_watermark_engine()
    return version


def _check_paths(
    body: C2PASignRequest, input_dirs: list[Path], output_dirs: list[Path]
) -> tuple[Path, Path]:
    """Return the request's input and output paths, resolved, once both pass the folder checks.

    Raises:
        HTTPException: 404 if there is no input file, else 400 naming the path that failed.
    """
    # os.path answers False where Path.is_file and Path.is_dir raise on an unsearchable folder
    media_input_path = _resolve_in(body.media_input_path, input_dirs, "InvalidMediaInputPath")
    if not os.path.isfile(media_input_path):
        raise HTTPException(status_code=404, detail="MediaInputPathNotFound")
    if not os.access(media_input_path, os.R_OK):
        raise HTTPException(status_code=400, detail="InvalidMediaInputPath")
    media_output_path = _resolve_in(body.media_output_path, output_dirs, "InvalidMediaOutputPath")
    if os.path.isdir(media_output_path) or not os.access(
        media_output_path.parent, os.W_OK | os.X_OK
    ):
        raise HTTPException(status_code=400, detail="InvalidMediaOutputPath")
    return media_input_path, media_output_path


def _resolve_in(path: str, folders: list[Path], error: str) -> Path:
    """Return ``path`` resolved, if it is absolute and inside one of ``folders``.

    Raises:
        HTTPException: 400 with ``error`` otherwise.
    """
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            resolved = candidate.resolve()
        except (OSError, ValueError, RuntimeError) as exc:
            # e.g. a NUL byte, an unencodable character or a symlink loop
            raise HTTPException(status_code=400, detail=error) from exc
        if any(resolved.is_relative_to(folder) for folder in folders):
            return resolved
    raise HTTPException(status_code=400, detail=error)
