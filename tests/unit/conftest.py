# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Fixtures for the unit tests: the engine, the credential folder, the browser, Trufo's task and
device answers, and its CA, as a test sets them; and the fields of a public result."""

import base64
import dataclasses
import datetime
import http.client
import importlib.abc
import os
import sys
import threading
import webbrowser
from pathlib import Path
from types import ModuleType, SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.hazmat.primitives.serialization.pkcs7 import serialize_certificates
from cryptography.x509.oid import NameOID

from trufo.util import credentials


class _FailingImport(importlib.abc.MetaPathFinder):
    """Fails importing ``module`` and the modules in it, as when ``missing`` is not installed."""

    def __init__(self, module, missing):
        self.module, self.missing = module, missing

    def find_spec(self, fullname, path, target=None):
        if fullname == self.module or fullname.startswith(f"{self.module}."):
            raise ModuleNotFoundError(f"No module named {self.missing!r}", name=self.missing)


class FakeEngine:
    """The engine (``tfprov``) as a unit test scripts it, in ``sys.modules`` for the SDK's own
    imports.

    ``generate_claim_remote`` returns ``signed``, ``embed`` returns ``watermarked``, and
    ``read_manifest_bytes`` returns ``b"store of "`` and the bytes of the file it reads; each
    records its function name, args and kwargs in ``calls``. ``bridge_available`` is what the
    C2PA bridge reports. ``older()`` puts in a ``generate_claim_remote`` without
    ``remote_manifest_settings`` and ``warning_stacklevel``, ``uninstall()`` marks the engine as
    not installed, and ``break_import(module, missing)`` makes importing ``module`` fail on a
    dependency of its own.
    """

    version = "9.9.9"

    def __init__(self, monkeypatch):
        self.calls = []
        self.signed = b"signed"
        self.watermarked = b"watermarked"
        self.bridge_available = True
        self._monkeypatch = monkeypatch
        modules = {
            "tfprov": {"__version__": self.version},
            "tfprov.c2pa_generator": {},
            "tfprov.c2pa_generator.remote_orchestrator": {
                "generate_claim_remote": self.generate_claim_remote
            },
            "tfprov.c2pa_rs_bridge": {},
            "tfprov.c2pa_rs_bridge.rs_bridge": {
                "is_available": lambda: self.bridge_available,
                "read_manifest_bytes": self.read_manifest_bytes,
            },
            "tfprov.util": {},
            "tfprov.util.av_format": {
                "get_media_probe_result": lambda media: SimpleNamespace(mime_type="image/png"),
                "get_extension": lambda mime_type: "png",
            },
            "tfprov.util.pawprint_import": {
                "WatermarkIdPackage": SimpleNamespace,
                "embed": self.embed,
            },
        }
        # the real engine's modules, if this environment has it, are out of reach meanwhile
        for name in [name for name in sys.modules if name.split(".")[0] == "tfprov"]:
            monkeypatch.delitem(sys.modules, name)
        for name, attributes in modules.items():
            module = ModuleType(name)
            # a package, so a module it does not hold is searched for
            module.__path__ = []
            vars(module).update(attributes)
            monkeypatch.setitem(sys.modules, name, module)
            parent, _, child = name.rpartition(".")
            if parent:
                setattr(sys.modules[parent], child, module)

    def generate_claim_remote(self, api_key, media_bytes, **kwargs):
        self.calls.append(
            SimpleNamespace(
                function="generate_claim_remote", args=(api_key, media_bytes), kwargs=kwargs
            )
        )
        return self.signed, []

    def embed(self, media_bytes, package, **options):
        self.calls.append(
            SimpleNamespace(function="embed", args=(media_bytes, package), kwargs=options)
        )
        return self.watermarked

    def read_manifest_bytes(self, *, path):
        self.calls.append(
            SimpleNamespace(function="read_manifest_bytes", args=(), kwargs={"path": path})
        )
        return b"store of " + Path(path).read_bytes()

    def older(self):
        def generate_claim_remote(
            api_key,
            media_bytes,
            *,
            actions,
            assertions,
            trufo_api_url,
            test,
            manifest_title=None,
            ingredient_title=None,
            branded_gp_id=None,
            manifest_settings=None,
            watermark_settings=None,
            signed_input_policy=None,
            signed_ingredient_policy=None,
            skip_manifest_storage=False,
        ):
            return self.generate_claim_remote(api_key, media_bytes)

        sys.modules["tfprov.c2pa_generator.remote_orchestrator"].generate_claim_remote = (
            generate_claim_remote
        )

    def uninstall(self):
        self.break_import("tfprov", "tfprov")

    def break_import(self, module, missing):
        parent, _, child = module.rpartition(".")
        if parent in sys.modules:
            self._monkeypatch.delattr(sys.modules[parent], child, raising=False)
        for name in [name for name in sys.modules if f"{name}.".startswith(f"{module}.")]:
            self._monkeypatch.delitem(sys.modules, name)
        failing = _FailingImport(module, missing)
        self._monkeypatch.setattr(sys, "meta_path", [failing, *sys.meta_path])


@pytest.fixture
def fake_engine(monkeypatch):
    """The engine as a unit test scripts it (see ``FakeEngine``), installed."""
    return FakeEngine(monkeypatch)


@pytest.fixture
def trufo_home(tmp_path, monkeypatch):
    """The ``.trufo`` folder in ``tmp_path``, holding the API keys and the session in place of the
    user's, with every ``TRUFO_*`` environment variable cleared."""
    home = tmp_path / ".trufo"
    monkeypatch.setattr(credentials, "CONFIG_DIR", home)
    monkeypatch.setattr(credentials, "CREDENTIALS_DIR", home / "credentials")
    monkeypatch.setattr(credentials, "SESSION_FILE", home / "session")
    for name in [name for name in os.environ if name.startswith("TRUFO_")]:
        monkeypatch.delenv(name)
    return home


@pytest.fixture
def browser(monkeypatch):
    """The user's browser in a loopback sign-in, in place of ``webbrowser.open``.

    It records each URL it is sent to in ``opened``. Unless ``available`` is False, it then
    requests in turn each ``(path, query)`` that ``visits`` returns for the URL's parameters, on
    the listener its ``redirect_uri`` names (a ``redirect_uri`` that is not http on 127.0.0.1
    fails the test), and records each answer's status and body in ``answers``; ``join()`` waits
    for its visits to end, and raises what one of them raised. By default it visits the callback
    with a code and the state it was sent.
    """
    threads, errors = [], []

    def join():
        for thread in threads:
            thread.join(timeout=10)
            assert not thread.is_alive(), "The browser's visits did not end."
        if errors:
            raise errors.pop(0)

    fake = SimpleNamespace(
        available=True,
        opened=[],
        answers=[],
        visits=lambda params: [("/callback", {"code": "the-code", "state": params["state"]})],
        join=join,
    )

    def visit(port, pages):
        try:
            for path, query in pages:
                # straight to the listener: no proxy, and no redirect followed
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                connection.request("GET", f"{path}?{urlencode(query)}")
                answer = connection.getresponse()
                fake.answers.append((answer.status, answer.read().decode()))
                connection.close()
        except Exception as error:
            errors.append(error)

    def open_browser(url):
        fake.opened.append(url)
        if not fake.available:
            return False
        params = {name: values[0] for name, values in parse_qs(urlsplit(url).query).items()}
        redirect = urlsplit(params["redirect_uri"])
        if (redirect.scheme, redirect.hostname) != ("http", "127.0.0.1") or not redirect.port:
            pytest.fail(f"Not a listener on this machine: {redirect.geturl()}", pytrace=False)
        threads.append(threading.Thread(target=visit, args=(redirect.port, fake.visits(params))))
        threads[-1].start()
        return True

    monkeypatch.setattr(webbrowser, "open", open_browser)
    yield fake
    join()


@pytest.fixture
def task_answer():
    """A function ``task_answer(status="succeeded", task_type="c2pa_sign", **result)`` that
    returns what Trufo's API answers for task ``task-1``: with a result when it succeeded, whose
    fields ``result`` replaces or adds to."""

    def answer(status="succeeded", task_type="c2pa_sign", **result):
        return {
            "task_id": "task-1",
            "task_type": task_type,
            "status": status,
            "startby_ts": "2026-09-19T12:05:00Z",
            "timeout_seconds": 60,
            "create_ts": "2026-09-19T12:00:00Z",
            "update_ts": "2026-09-19T12:00:01Z",
            "file_size_bytes": 123,
            "file_mime_type": "image/jpeg",
            "result": (
                {
                    "media_output_s3": "output-reference",
                    "download_url": "https://download.example/output",
                    "expires_ts": "2026-09-20T12:00:00Z",
                    "cid": "content-1",
                    "wid": "watermark-1",
                    **result,
                }
                if status == "succeeded"
                else None
            ),
        }

    return answer


@pytest.fixture
def assert_frozen_fields():
    """A function ``assert_frozen_fields(result)`` that checks that ``result``, a public result,
    cannot be changed, and returns its field names in order."""

    def names(result):
        names = [field.name for field in dataclasses.fields(result)]
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(result, names[0], None)
        return names

    return names


@pytest.fixture
def device_answer():
    """What Trufo's API answers when a device sign-in starts."""
    return {
        "device_code": "device-1",
        "user_code": "ABCD-1234",
        "verification_uri": "https://app.example.test/device",
        "verification_uri_complete": "https://app.example.test/device?code=ABCD-1234",
        "expires_in": 600,
        "interval": 5,
    }


def _certificate(subject, public_key, issuer, issuer_key, *, ca=False, serial=None):
    """A certificate for ``public_key``, valid for a day, issued by ``issuer_key``."""
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer)]))
        .public_key(public_key)
        .serial_number(serial or x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
    )
    if ca:
        builder = builder.add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
    ed = isinstance(issuer_key, ed25519.Ed25519PrivateKey)
    return builder.sign(issuer_key, None if ed else hashes.SHA256())


@pytest.fixture
def certificate():
    """A function ``certificate(subject, public_key, issuer, issuer_key, *, ca=False,
    serial=None)`` that returns a certificate for ``public_key``, valid for a day, issued by
    ``issuer_key``; a CA's when ``ca``."""
    return _certificate


@pytest.fixture(scope="session")
def est_ca():
    """Trufo's CA, as a test scripts it: ``answer(request)`` is its EST answer, a base64 PKCS#7
    holding a certificate for the CSR's key issued by ``issuing``, then ``root`` and
    ``issuing``, its own certificates."""
    root_key = ec.generate_private_key(ec.SECP256R1())
    issuing_key = ec.generate_private_key(ec.SECP256R1())
    root = _certificate("Root CA", root_key.public_key(), "Root CA", root_key, ca=True)
    issuing = _certificate("Issuing CA", issuing_key.public_key(), "Root CA", root_key, ca=True)

    def answer(request):
        csr = x509.load_der_x509_csr(base64.b64decode(request.body))
        assert csr.is_signature_valid
        leaf = _certificate("Leaf", csr.public_key(), "Issuing CA", issuing_key)
        return base64.b64encode(serialize_certificates([leaf, root, issuing], Encoding.DER))

    return SimpleNamespace(answer=answer, root=root, issuing=issuing)
