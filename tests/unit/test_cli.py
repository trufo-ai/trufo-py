# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The trufo command: API keys, signing in and out, instances, credentials and certificates."""

import stat
import sys

import pytest
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from trufo import generate_keypair
from trufo.api.endpoints import TRUFO_API_URL, TRUFO_CA_URL
from trufo.crypt.algorithms import SigningAlgorithm
from trufo.intf.cli import main
from trufo.util.credentials import load_api_key, load_session, save_api_key

TOKENS = {"access_token": "access-1", "refresh_token": "refresh-1"}
NO_SESSION = (
    "No session found. Run 'trufo login' or set TRUFO_ACCESS_TOKEN + TRUFO_REFRESH_TOKEN.\n"
)


@pytest.fixture
def trufo(monkeypatch, capsys):
    """A function ``trufo(*argv)`` that runs the command and returns its exit code, standard
    output and standard error."""

    def run(*argv):
        monkeypatch.setattr(sys, "argv", ["trufo", *argv])
        try:
            main()
            code = 0
        except SystemExit as exc:
            code = exc.code
        return code, *capsys.readouterr()

    return run


def test_set_api_key(trufo_home, trufo):
    assert trufo("set-api-key", "tsa", "key-1") == (0, "tsa API key saved.\n", "")
    assert load_api_key("tsa") == "key-1"
    code, _, error = trufo("set-api-key", "tps", "key-2")
    assert (code, "invalid choice: 'tps'" in error) == (2, True)


@pytest.mark.parametrize("device", [False, True])
def test_login_and_logout(trufo_api, trufo_home, browser, device_answer, trufo, device):
    argv = ["login", "--device"] if device else ["login"]
    no_key = "No trufo-api key configured. Run: trufo set-api-key trufo-api <KEY>\n"
    assert trufo(*argv) == (1, "", no_key)
    save_api_key("trufo-api", "api-key")
    trufo_api.answer("POST", f"{TRUFO_API_URL}/account/loopback/token", TOKENS)
    trufo_api.answer("POST", f"{TRUFO_API_URL}/account/device/authorize", device_answer)
    trufo_api.answer("POST", f"{TRUFO_API_URL}/account/device/token", TOKENS)

    code, output, _ = trufo(*argv)

    assert (code, output.endswith("Login successful.\n")) == (0, True)
    assert (len(browser.opened), {r.headers["X-API-Key"] for r in trufo_api.requests}) == (
        int(not device),
        {"api-key"},
    )
    session = load_session()
    assert (session.access_token, session.refresh_token) == ("access-1", "refresh-1")
    assert trufo("logout") == (0, "Session cleared.\n", "")
    with pytest.raises(RuntimeError, match="No session found"):
        load_session()


def test_instance_commands_need_a_session(trufo_api, trufo_home, monkeypatch, tmp_path, trufo):
    public_pem = generate_keypair(SigningAlgorithm.ES256)[1].decode()
    (tmp_path / "public.pem").write_text(public_pem)
    add_gpi = ["add-gpi", "--gp", "gp_1", "--name", "Instance"]
    register_gpic = ["register-gpic", "--gpi", "gpi_1", "--label", "Key", "--alg", "ES256"]
    register_gpic += ["--pem", str(tmp_path / "public.pem")]
    # nothing is sent without a session: a request would fail the test
    assert trufo(*add_gpi) == trufo(*register_gpic) == (1, "", NO_SESSION)

    monkeypatch.setenv("TRUFO_ACCESS_TOKEN", "access-1")
    monkeypatch.setenv("TRUFO_REFRESH_TOKEN", "refresh-1")
    trufo_api.answer("POST", f"{TRUFO_API_URL}/gproduct/instance/create", {"gpi_id": "gpi_1"})
    trufo_api.answer(
        "POST", f"{TRUFO_API_URL}/gproduct/instance/credential/register", {"gpic_id": "gpic_1"}
    )
    assert trufo(*add_gpi) == (0, "Instance created: gpi_1\n", "")
    assert trufo(*register_gpic) == (0, "Credential registered: gpic_1\n", "")
    assert len(trufo_api.requests) == 2
    assert trufo_api.requests[-1].json["public_key_pem"] == public_pem


def test_get_c2pa_cert(trufo_api, trufo_home, est_ca, tmp_path, trufo):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/ra/c2pa/csr-jwt", {"csr_jwt": "csr-jwt"})
    trufo_api.answer("POST", f"{TRUFO_CA_URL}/.well-known/est/c2pa-l1/simpleenroll", est_ca.answer)
    (tmp_path / "instance.pem").write_bytes(generate_keypair(SigningAlgorithm.ES256)[0])
    out = tmp_path / "certificates"
    argv = ["get-c2pa-cert", "--gpi", "gpi_1", "--gpic", "gpic_1"]
    argv += ["--instance-key", str(tmp_path / "instance.pem"), "--out-dir", str(out)]
    key_file, chain_file = out / "leaf_key.pem", out / "cert_chain.pem"

    def written_key():
        """The key written, whose certificate the chain written starts with."""
        key = load_pem_private_key(key_file.read_bytes(), password=None)
        leaf, issuing = x509.load_pem_x509_certificates(chain_file.read_bytes())
        assert (leaf.public_key(), issuing) == (key.public_key(), est_ca.issuing)
        return key

    assert trufo(*argv) == (0, f"Leaf key:   {key_file}\nCert chain: {chain_file}\n", "")
    key = written_key()
    assert isinstance(key.curve, ec.SECP256R1)
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    # refused without --overwrite, before any request, whichever of the files exists
    files = {path: path.read_bytes() for path in (key_file, chain_file)}
    sent = len(trufo_api.requests)
    for existing in [(key_file,), (chain_file,), (key_file, chain_file)]:
        for path in files:
            path.unlink(missing_ok=True)
        for path in existing:
            path.write_bytes(files[path])
        errors = "".join(f"Error: file already exists: {path}\n" for path in existing)
        assert trufo(*argv) == (1, "", f"{errors}Use --overwrite to overwrite existing files.\n")
        assert {path: path.read_bytes() for path in files if path.exists()} == {
            path: files[path] for path in existing
        }
        assert len(trufo_api.requests) == sent
    assert trufo(*argv, "--overwrite")[0] == 0
    assert written_key().public_key() != key.public_key()
