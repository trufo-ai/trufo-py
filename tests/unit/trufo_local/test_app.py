# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the trufo-local service: path checks, error mapping and sign slots."""

import importlib.metadata
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("tfprov", minversion="2.2.0")

import app as service  # noqa: E402
import tfprov  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from tfprov.c2pa_generator.trufo_actions import WatermarkApplyError  # noqa: E402
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
def no_watermark_engine(monkeypatch):
    """Report the watermark engine as not installed, whatever this environment has."""
    version = importlib.metadata.version

    def fake_version(name):
        if name == "trufo-pawprint":
            raise importlib.metadata.PackageNotFoundError(name)
        return version(name)

    monkeypatch.setattr(importlib.metadata, "version", fake_version)


@pytest.fixture
def watermark_engine(no_watermark_engine, monkeypatch):
    """Report the watermark engine as installed; list it before client, which reads it at start."""
    version = importlib.metadata.version
    monkeypatch.setattr(
        importlib.metadata,
        "version",
        lambda name: "0.5.2" if name == "trufo-pawprint" else version(name),
    )
    monkeypatch.setattr(service, "require_watermark_engine", lambda: None)


@pytest.fixture
def client(folders, engine, no_watermark_engine):
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
        "signed_input_policy": "keep",
        "signed_ingredient_policy": "auto",
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


@pytest.mark.parametrize("field", ["signed_input_policy", "signed_ingredient_policy"])
def test_bad_policy(sign, engine, field):
    assert sign(**{field: "bogus"}).status_code == 422
    assert engine.calls == []


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
        pytest.param(WatermarkApplyError("Not marked."), 400, "Not marked.", id="watermark failed"),
        pytest.param(_remove_input, 404, "MediaInputPathNotFound", id="input removed"),
        pytest.param(FileNotFoundError(), 500, "Internal server error.", id="other file"),
        pytest.param(RuntimeError(), 500, "Internal server error.", id="unexpected"),
        pytest.param(NotImplementedError(), 500, "Internal server error.", id="not implemented"),
    ],
)
def test_engine_errors(sign, engine, side_effect, status, detail):
    engine.side_effect = side_effect
    response = sign()
    assert (response.status_code, response.json()) == (status, {"detail": detail})


def test_watermark_engine_installed(watermark_engine, client, sign, engine):
    actions = [["watermark", {"effort": "require"}]]
    response = sign(actions=actions)
    assert response.status_code == 200
    assert response.json()["warnings"] == [
        "The watermark 'effort' parameter is deprecated; use 'effort_policy'.",
        "A warning.",
    ]
    assert engine.calls[0]["actions"] == actions
    assert client.get("/health").json()["watermark_engine_version"] == "0.5.2"


@pytest.mark.parametrize(
    "params, status, detail",
    [
        pytest.param(
            {"wid_allocation_mode": "per_asset"},
            501,
            "Per-asset watermark ID allocation is not supported.",
            id="per asset",
        ),
        pytest.param({"mode": "bogus"}, 400, "Invalid watermark mode.", id="bad mode"),
    ],
)
def test_watermark_refused(watermark_engine, sign, engine, params, status, detail):
    response = sign(actions=[["watermark", params]])
    assert (response.status_code, response.json()) == (status, {"detail": detail})
    assert engine.calls == []


def test_unimportable_watermark_engine_fails_the_start(watermark_engine, folders, monkeypatch):
    def require_watermark_engine():
        raise ImportError

    monkeypatch.setattr(service, "require_watermark_engine", require_watermark_engine)
    with pytest.raises(ImportError), TestClient(service.app):
        pass


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


@pytest.mark.parametrize("settings", [{}, {"profile": "fast", "device": "cpu"}])
def test_watermark_settings_forwarded_separately(sign, engine, settings):
    assert sign(watermark_settings=settings).status_code == 200
    assert engine.calls[0]["watermark_settings"] == settings
    assert engine.calls[0]["actions"] == []


@pytest.mark.parametrize(
    "settings", [{"profile": "other"}, {"device": False}, {"device": "cuda:01"}, {"unknown": 1}]
)
def test_invalid_watermark_settings_refused_before_paths(sign, engine, settings):
    response = sign(watermark_settings=settings, media_input_path="missing")
    assert response.status_code == 400
    assert "watermark" in response.json()["detail"].lower()
    assert engine.calls == []


def test_fresh_app_with_legacy_engine_symbols(folders):
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from trufo import c2pa
from trufo.c2pa import watermark
from tfprov.c2pa_generator import cg_request, remote_orchestrator
for module in (c2pa, watermark, cg_request):
    for name in ('WatermarkSettings', 'WatermarkProfile', 'normalize_watermark_settings'):
        if hasattr(module, name): delattr(module, name)
def legacy(api_key, **kwargs):
    assert 'watermark_settings' not in kwargs
    return str(kwargs['media_output_path']), []
remote_orchestrator.generate_claim_remote = legacy
sys.path.insert(0, sys.argv[1])
import app
app._watermark_engine_version = lambda: None
folder = Path(sys.argv[2])
body = {'media_input_path': str(folder/'in/photo.jpg'),
        'media_output_path': str(folder/'out/signed.jpg'), 'actions': []}
with TestClient(app.app) as client:
    assert client.get('/health').status_code == 200
    response = client.post('/c2pa/sign', json=body, headers={'X-API-Key': 'key'})
    assert response.status_code == 200, response.text
    body['watermark_settings'] = {}
    response = client.post('/c2pa/sign', json=body, headers={'X-API-Key': 'key'})
    assert response.status_code == 400
    assert response.json()['detail'] == 'Watermark settings require trufo-provenance 2.3 or later.'
""",
            str(Path(service.__file__).parent),
            str(folders),
        ],
        env=os.environ.copy(),
        check=True,
    )
