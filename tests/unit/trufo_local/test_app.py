# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the trufo-local service: path checks, error mapping and sign slots."""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("tfprov", minversion="2.1.1")

import app as service  # noqa: E402
import tfprov  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from tfprov.c2pa_py.errors import RedactionError, RemoteSignError  # noqa: E402

API_KEY = "c2pa-sign-test:key"
TRUFO_API_URL = "https://test.api.trufo.ai"
VERSION = "9.9.9"
IN, OUT = "media_input_path", "media_output_path"
BAD_IN, BAD_OUT = "InvalidMediaInputPath", "InvalidMediaOutputPath"
FIELD_ERRORS = [{"type": "missing", "loc": ["body", "actions"], "msg": "Field required"}]
NOT_AS_ROOT = pytest.mark.skipif(os.geteuid() == 0, reason="root reads and writes any file")


@pytest.fixture
def folders(tmp_path, monkeypatch):
    """Listed folders in/, out/ and both/, and in-x/ beside them, unlisted."""
    for name in ("in", "out", "both", "in-x"):
        (tmp_path / name).mkdir()
    for name in ("in/photo.jpg", "in-x/photo.jpg", "out/photo.jpg"):
        (tmp_path / name).write_bytes(b"media")
    (tmp_path / "in/escape.jpg").symlink_to(tmp_path / "in-x/photo.jpg")
    (tmp_path / "out/escape.jpg").symlink_to(tmp_path / "in-x/signed.jpg")
    monkeypatch.setenv("TRUFO_LOCAL_INPUT_DIRS", f"{tmp_path}/in:{tmp_path}/both")
    monkeypatch.setenv("TRUFO_LOCAL_OUTPUT_DIRS", f"{tmp_path}/out:{tmp_path}/both")
    monkeypatch.setenv("TRUFO_API_URL", TRUFO_API_URL)
    monkeypatch.setenv("TRUFO_LOCAL_VERSION", VERSION)
    return tmp_path


@pytest.fixture
def engine(monkeypatch):
    """Replace the engine call with a fake that records it, then raises or runs ``side_effect``."""
    fake = SimpleNamespace(calls=[], side_effect=None)

    def generate_claim_remote(api_key, **kwargs):
        fake.calls.append({"api_key": api_key, **kwargs})
        if isinstance(fake.side_effect, Exception):
            raise fake.side_effect
        if fake.side_effect is not None:
            fake.side_effect(kwargs)
        return str(kwargs["media_output_path"].with_suffix(".png")), ["A warning."]

    monkeypatch.setattr(service, "generate_claim_remote", generate_claim_remote)
    return fake


@pytest.fixture
def client(folders, engine):
    with TestClient(service.app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def sign(client, folders):
    """Post a sign of in/photo.jpg to out/signed.jpg, with ``fields`` replacing body fields."""

    def post(api_key=API_KEY, **fields):
        body = {IN: f"{folders}/in/photo.jpg", OUT: f"{folders}/out/signed.jpg", **fields}
        headers = {"X-API-Key": api_key} if api_key else {}
        return client.post("/c2pa/sign", json={"actions": [], **body}, headers=headers)

    return post


def _remove_input(kwargs):
    kwargs["media_input_path"].unlink()
    raise FileNotFoundError


@pytest.mark.parametrize(
    "fields, status, detail",
    [
        pytest.param({IN: "in/photo.jpg"}, 400, BAD_IN, id="relative input"),
        pytest.param({OUT: "out/signed.jpg"}, 400, BAD_OUT, id="relative output"),
        pytest.param({IN: "{tmp}/in/../in-x/photo.jpg"}, 400, BAD_IN, id="dot-dot"),
        pytest.param({IN: "{tmp}/in/photo\x00.jpg"}, 400, BAD_IN, id="nul"),
        pytest.param({IN: "{tmp}/in/escape.jpg"}, 400, BAD_IN, id="input link out"),
        pytest.param({OUT: "{tmp}/out/escape.jpg"}, 400, BAD_OUT, id="output link out"),
        pytest.param({IN: "{tmp}/in-x/photo.jpg"}, 400, BAD_IN, id="name prefix"),
        pytest.param({IN: "{tmp}/out/photo.jpg"}, 400, BAD_IN, id="input in out"),
        pytest.param({OUT: "{tmp}/in/signed.jpg"}, 400, BAD_OUT, id="output in in"),
        pytest.param({IN: "/etc/passwd"}, 400, BAD_IN, id="system input"),
        pytest.param({OUT: "/etc/passwd"}, 400, BAD_OUT, id="system output"),
        pytest.param({IN: "{tmp}/in/missing.jpg"}, 404, "MediaInputPathNotFound", id="missing"),
        pytest.param({OUT: "{tmp}/out"}, 400, BAD_OUT, id="output is a folder"),
        pytest.param({OUT: "{tmp}/out/missing/signed.jpg"}, 400, BAD_OUT, id="no folder"),
        pytest.param({IN: "{tmp}/in/secret.jpg"}, 400, BAD_IN, id="unreadable", marks=NOT_AS_ROOT),
        pytest.param({OUT: "{tmp}/out/ro/a.jpg"}, 400, BAD_OUT, id="unwritable", marks=NOT_AS_ROOT),
        pytest.param({"api_key": None}, 401, "MissingAuthentication", id="no key"),
        pytest.param(
            {"actions": [["watermark", {}]]}, 400, "WatermarkNotAvailable", id="watermark"
        ),
    ],
)
def test_refused_before_the_engine(sign, folders, engine, fields, status, detail):
    (folders / "in/secret.jpg").touch(mode=0o000)
    (folders / "out/ro").mkdir(mode=0o555)
    response = sign(
        **{k: v.format(tmp=folders) if k in (IN, OUT) else v for k, v in fields.items()}
    )
    assert (response.status_code, response.json()) == (status, {"detail": detail})
    assert engine.calls == []


def test_accepted(sign, folders, engine):
    (folders / "in/link.jpg").symlink_to(folders / "in/photo.jpg")
    (folders / "both/signed.jpg").write_bytes(b"old")
    fields = {
        "actions": [["publish", {}]],
        "assertions": [["creation", {}]],
        "manifest_title": "Signed photo",
        "ingredient_title": "photo.jpg",
        "manifest_settings": {"all_actions_included": True},
        "branded_gp_id": "gp_1",
    }
    response = sign(
        **{IN: f"{folders}/in/link.jpg", OUT: f"{folders}/both/signed.jpg"},
        unknown_field="ignored",
        **fields,
    )
    assert (response.status_code, response.json()) == (
        200,
        {"media_output_path": f"{folders}/both/signed.png", "warnings": ["A warning."]},
    )
    assert engine.calls == [
        {
            "api_key": API_KEY,
            IN: folders / "in/photo.jpg",
            OUT: folders / "both/signed.jpg",
            "trufo_api_url": TRUFO_API_URL,
            **fields,
        }
    ]


@pytest.mark.parametrize(
    "side_effect, status, detail",
    [
        pytest.param(
            RemoteSignError("Refused.", status_code=403, detail="MissingOrganizationValidation"),
            403,
            "MissingOrganizationValidation",
            id="trufo 403",
        ),
        pytest.param(
            RemoteSignError("Refused.", status_code=422, detail=FIELD_ERRORS),
            422,
            FIELD_ERRORS,
            id="trufo 422 list",
        ),
        pytest.param(
            RemoteSignError("Failed.", status_code=500, detail="Internal server error."),
            502,
            "TrufoAPIError",
            id="trufo 500",
        ),
        pytest.param(RemoteSignError("Unreachable."), 502, "TrufoAPIError", id="unreachable"),
        pytest.param(RemoteSignError("Not JSON.", status_code=400), 502, "TrufoAPIError", id="400"),
        pytest.param(ValueError("Refused."), 400, "Refused.", id="engine refusal"),
        pytest.param(RedactionError("Refused."), 400, "Refused.", id="redaction"),
        pytest.param(_remove_input, 404, "MediaInputPathNotFound", id="input removed"),
        pytest.param(FileNotFoundError(), 500, "Internal server error.", id="other file"),
        pytest.param(RuntimeError(), 500, "Internal server error.", id="unexpected"),
    ],
)
def test_engine_errors(sign, engine, side_effect, status, detail):
    engine.side_effect = side_effect
    response = sign()
    assert (response.status_code, response.json()) == (status, {"detail": detail})


def test_two_signs_at_a_time_while_health_answers(client, sign, folders, engine):
    entered, release = threading.Semaphore(0), threading.Event()

    def block(kwargs):
        entered.release()
        assert release.wait(10)

    engine.side_effect = block
    with ThreadPoolExecutor(4) as pool:
        signs = [pool.submit(sign, **{OUT: f"{folders}/out/{n}.jpg"}) for n in range(3)]
        assert entered.acquire(timeout=10) and entered.acquire(timeout=10)
        health = pool.submit(client.get, "/health").result(timeout=10)
        assert health.json() == {
            "status": "healthy",
            "version": VERSION,
            "engine_version": tfprov.__version__,
        }
        # can only miss a bug, never fail a correct build
        assert not entered.acquire(timeout=0.5)
        release.set()
        assert [future.result(timeout=10).status_code for future in signs] == [200] * 3


def test_docs_are_off(client):
    assert client.get("/docs").status_code == client.get("/openapi.json").status_code == 404


def test_gone_client_is_not_signed(client, folders, engine):
    body = {IN: f"{folders}/in/photo.jpg", OUT: f"{folders}/out/signed.jpg", "actions": []}
    messages = [{"type": "http.request", "body": json.dumps(body).encode()}]
    sent = []

    async def receive():
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    headers = [(b"content-type", b"application/json"), (b"x-api-key", API_KEY.encode())]
    scope = {"type": "http", "method": "POST", "path": "/c2pa/sign", "query_string": b""}
    client.portal.call(service.app, {**scope, "headers": headers}, receive, send)
    # the request reached the slot: an earlier refusal would carry another status
    assert sent[0]["status"] == 499
    assert engine.calls == []
