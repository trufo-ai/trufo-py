# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Certificates: instances and credentials, requests to the registration authority, CSRs, EST
enrollment and the certificate chain."""

import base64
import uuid

import jwt as pyjwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_private_key,
)
from cryptography.hazmat.primitives.serialization.pkcs7 import (
    load_der_pkcs7_certificates,
    serialize_certificates,
)
from cryptography.x509.oid import NameOID

from trufo import (
    create_instance,
    generate_keypair,
    register_credential,
    request_c2pa_cert,
    request_c2pa_cert_test,
    request_c2pa_dummy_cert,
    request_cawg_dummy_cert,
    request_cawg_interim_cert,
)
from trufo.api.endpoints import TRUFO_API_URL, TRUFO_CA_URL
from trufo.api.session import TrufoSession
from trufo.crypt.algorithms import SigningAlgorithm
from trufo.crypt.tca_certs import (
    DUMMY_HMAC_SECRET,
    LeafType,
    build_csr,
    est_enroll,
    extract_cert_chain,
)

LEAF_PEM, LEAF_PUBLIC_PEM = generate_keypair(SigningAlgorithm.ES256)


def _name(common_name):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _pkcs7(certificates):
    return base64.b64encode(serialize_certificates(certificates, Encoding.DER))


def _csr_jwt(request):
    """The CSR JWT an EST request authenticates with, as an HTTP Basic password."""
    scheme, credential = request.headers["Authorization"].split()
    user, _, password = base64.b64decode(credential).decode().partition(":")
    assert (scheme, user) == ("Basic", "")
    return password


def _assert_chain(chain_pem, est_ca, leaf_public_pem=LEAF_PUBLIC_PEM):
    """The chain is the leaf for the key, then the issuing CA, without the root."""
    leaf, issuing = x509.load_pem_x509_certificates(chain_pem)
    assert leaf.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo) == (
        leaf_public_pem
    )
    assert issuing == est_ca.issuing


def test_est_enroll(trufo_api):
    url = f"{TRUFO_CA_URL}/.well-known/est/c2pa-l1/simpleenroll"
    trufo_api.answer("POST", url, b"base64-pkcs7", (400, {"detail": "Invalid CSR."}))

    assert est_enroll("csr-jwt", b"csr-der", "c2pa-l1") == b"base64-pkcs7"
    (request,) = trufo_api.requests
    assert request.body == base64.b64encode(b"csr-der").decode()
    assert request.headers["Content-Type"] == "application/pkcs10"
    assert _csr_jwt(request) == "csr-jwt"
    with pytest.raises(RuntimeError, match=r"EST enrollment failed \(400\): Invalid CSR."):
        est_enroll("csr-jwt", b"csr-der", "c2pa-l1")


@pytest.mark.parametrize(
    "request_cert, api_url, ca_url",
    [
        (request_c2pa_cert, "https://api.trufo.ai", "https://ca.trufo.ai"),
        (request_c2pa_cert_test, "https://test.api.trufo.ai", "https://test.ca.trufo.ai"),
    ],
)
@pytest.mark.parametrize("validity_days", [None, 30])
def test_request_c2pa_cert(trufo_api, est_ca, request_cert, api_url, ca_url, validity_days):
    trufo_api.answer("POST", f"{api_url}/ra/c2pa/csr-jwt", {"csr_jwt": "csr-jwt"})
    trufo_api.answer("POST", f"{ca_url}/.well-known/est/c2pa-l1/simpleenroll", est_ca.answer)
    instance_pem, _ = generate_keypair(SigningAlgorithm.ES256)

    chain = request_cert("gpi_1", "gpic_1", instance_pem, LEAF_PEM, validity_days=validity_days)

    _assert_chain(chain, est_ca)
    ra, est = trufo_api.requests
    assert {name: value for name, value in ra.json.items() if name != "client_assertion"} == {
        "leaf_type": "c2pa-l1",
        **({} if validity_days is None else {"validity_days": validity_days}),
    }
    # the client assertion in the body is the only credential
    assert not {"X-API-Key", "Authorization"} & set(ra.headers)
    assert _csr_jwt(est) == "csr-jwt"


@pytest.mark.parametrize(
    "algorithm, key_form",
    [
        (SigningAlgorithm.ES256, "pem-str"),
        (SigningAlgorithm.ES256, "aws-kms"),
        (SigningAlgorithm.ES256, "gcp-kms"),
        (SigningAlgorithm.EDDSA, "pem-bytes"),
    ],
)
def test_client_assertion(trufo_api, est_ca, kms_keys, algorithm, key_form):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/ra/c2pa/csr-jwt", {"csr_jwt": "csr-jwt"})
    trufo_api.answer("POST", f"{TRUFO_CA_URL}/.well-known/est/c2pa-l1/simpleenroll", est_ca.answer)
    private_pem, public_pem = generate_keypair(algorithm)
    instance_key = {"pem-str": bytes.decode, "pem-bytes": bytes, **kms_keys}[key_form](private_pem)

    request_c2pa_cert("gpi_1", "gpic_1", instance_key, LEAF_PEM)

    assert len(trufo_api.requests) == 2
    assertion = trufo_api.requests[0].json["client_assertion"]
    claims = pyjwt.decode(
        assertion, public_pem, algorithms=[algorithm.alg_name], audience="trufo-ra"
    )
    assert (claims["iss"], claims["sub"], claims["exp"] - claims["iat"]) == ("gpi_1", "gpic_1", 60)


def test_instance_and_credential(trufo_api):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/gproduct/instance/create", {"gpi_id": "gpi_1"})
    trufo_api.answer(
        "POST", f"{TRUFO_API_URL}/gproduct/instance/credential/register", {"gpic_id": "gpic_1"}
    )
    session = TrufoSession(access_token="access-1")

    assert create_instance(session, "gp_1", "instance") == "gpi_1"
    assert register_credential(session, "gpi_1", "label", "EdDSA", "public-pem") == "gpic_1"
    assert [r.json for r in trufo_api.requests] == [
        {"gp_id": "gp_1", "name": "instance"},
        {
            "gpi_id": "gpi_1",
            "public_key_pem": "public-pem",
            "key_algorithm": "EdDSA",
            "label": "label",
        },
    ]


@pytest.mark.parametrize("validity_days, body", [(None, {}), (30, {"validity_days": 30})])
def test_cawg_interim_cert(trufo_api, est_ca, validity_days, body):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/ra/cawg-interim/csr-jwt", {"csr_jwt": "csr-jwt"})
    trufo_api.answer(
        "POST", f"{TRUFO_CA_URL}/.well-known/est/cawg-interim/simpleenroll", est_ca.answer
    )

    chain = request_cawg_interim_cert(
        TrufoSession(access_token="access-1"), LEAF_PEM, validity_days
    )

    _assert_chain(chain, est_ca)
    ra, est = trufo_api.requests
    assert ra.json == body
    assert _csr_jwt(est) == "csr-jwt"


def _dummy_claims(request):
    """The claims of a dummy CSR JWT, checked against the public dummy secret."""
    assert DUMMY_HMAC_SECRET == "hello-trufo"
    claims = pyjwt.decode(
        _csr_jwt(request), "hello-trufo", algorithms=["HS256"], audience="tca-est"
    )
    assert (claims["iss"], claims["exp"] - claims["iat"]) == ("trufo", 300)
    return claims


@pytest.mark.parametrize(
    "leaf_type, kwargs, subject",
    [
        (LeafType.C2PA_L1_DUMMY, {}, {"O": "Org", "CN": "CN"}),
        (
            LeafType.C2PA_L2_DUMMY,
            {"country": "US", "record_id": "rid-1"},
            {"O": "Org", "CN": "CN", "C": "US"},
        ),
    ],
)
def test_dummy_c2pa_cert(trufo_api, est_ca, leaf_type, kwargs, subject):
    trufo_api.answer(
        "POST", f"{TRUFO_CA_URL}/.well-known/est/{leaf_type.value}/simpleenroll", est_ca.answer
    )

    _assert_chain(request_c2pa_dummy_cert("Org", "CN", LEAF_PEM, leaf_type, **kwargs), est_ca)

    claims = _dummy_claims(*trufo_api.requests)
    assert (claims["leaf_type"], claims["distinguished_name"]) == (leaf_type.value, subject)
    if "record_id" in kwargs:
        assert claims["record_id"] == kwargs["record_id"]
    else:
        assert uuid.UUID(claims["record_id"]).version == 7
    assert uuid.UUID(claims["instance_id"].removeprefix("gpi_")).version == 7
    # a dummy leaf type only, and refused before sending
    with pytest.raises(ValueError, match="must be a C2PA dummy type"):
        request_c2pa_dummy_cert("Org", "CN", LEAF_PEM, LeafType.C2PA_L1)


@pytest.mark.parametrize(
    "kwargs, subject",
    [({}, {"O": "Org", "CN": "CN"}), ({"country": "US"}, {"O": "Org", "CN": "CN", "C": "US"})],
)
def test_dummy_cawg_cert(trufo_api, est_ca, kwargs, subject):
    trufo_api.answer(
        "POST", f"{TRUFO_CA_URL}/.well-known/est/cawg-interim-test/simpleenroll", est_ca.answer
    )

    _assert_chain(request_cawg_dummy_cert("Org", "CN", LEAF_PEM, **kwargs), est_ca)

    claims = _dummy_claims(*trufo_api.requests)
    assert (claims["leaf_type"], claims["distinguished_name"]) == ("cawg-interim-test", subject)
    assert (claims["record_id"], claims["instance_id"]) == ("", "")


def test_chain_order(certificate):
    # CA certificates of one length, so the PKCS#7, a DER set sorted by encoding, holds them by
    # serial number: the issuing CA before the CA it issued
    keys = [ed25519.Ed25519PrivateKey.generate() for _ in range(3)]
    root = certificate("CA 0", keys[0].public_key(), "CA 0", keys[0], ca=True, serial=1)
    issuing = certificate("CA 1", keys[1].public_key(), "CA 0", keys[0], ca=True, serial=2)
    sub = certificate("CA 2", keys[2].public_key(), "CA 1", keys[1], ca=True, serial=3)
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf = certificate("Leaf", leaf_key.public_key(), "CA 2", keys[2])
    pkcs7 = _pkcs7([leaf, sub, issuing, root])
    held = load_der_pkcs7_certificates(base64.b64decode(pkcs7))
    assert held.index(issuing) < held.index(sub)

    chain = x509.load_pem_x509_certificates(extract_cert_chain(pkcs7))
    assert chain == [leaf, sub, issuing]

    self_signed = certificate("Only", leaf_key.public_key(), "Only", leaf_key)
    assert x509.load_pem_x509_certificates(extract_cert_chain(_pkcs7([self_signed]))) == [
        self_signed
    ]


def test_bad_pkcs7():
    with pytest.raises(ValueError):
        extract_cert_chain(base64.b64encode(b"not-valid-pkcs7"))
    # a SignedData whose certificate set is present and empty (A0 00)
    empty = (
        "3025 06092a864886f70d010702 a018 3016 020101 3100 300b 06092a864886f70d010701 a000 3100"
    )
    with pytest.raises(RuntimeError, match=r"^PKCS#7 response contained no certificates\.$"):
        extract_cert_chain(base64.b64encode(bytes.fromhex(empty)))


@pytest.mark.parametrize(
    "algorithm, form",
    [
        (SigningAlgorithm.ES256, "pem"),
        (SigningAlgorithm.ES256, "str-path"),
        (SigningAlgorithm.ES384, "path"),
        (SigningAlgorithm.ES512, "key"),
        (SigningAlgorithm.ES256, "aws-kms"),
        (SigningAlgorithm.ES384, "aws-kms"),
        (SigningAlgorithm.ES256, "gcp-kms"),
        (SigningAlgorithm.ES384, "gcp-kms"),
    ],
)
def test_build_csr(tmp_path, kms_keys, algorithm, form):
    private_pem, public_pem = generate_keypair(algorithm)
    path = tmp_path / "key.pem"
    path.write_bytes(private_pem)
    forms = {
        "pem": lambda pem: pem,
        "str-path": lambda pem: str(path),
        "path": lambda pem: path,
        "key": lambda pem: load_pem_private_key(pem, password=None),
        **kms_keys,
    }

    csr = x509.load_der_x509_csr(build_csr(forms[form](private_pem)))

    assert csr.is_signature_valid
    assert csr.subject == _name("placeholder")
    assert (
        csr.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo) == public_pem
    )
    assert csr.signature_hash_algorithm.name == algorithm.hash_alg.lower()


def test_build_csr_refusals():
    with pytest.raises(TypeError, match="Unsupported private_key_signer type"):
        build_csr(123)
    with pytest.raises(ValueError):
        build_csr(b"not a pem")


def test_ra_refusal(trufo_api):
    trufo_api.answer("POST", f"{TRUFO_API_URL}/ra/c2pa/csr-jwt", (403, {"detail": "Revoked."}))
    instance_pem, _ = generate_keypair(SigningAlgorithm.ES256)
    # nothing is enrolled: a request to the CA would fail the test
    with pytest.raises(RuntimeError, match=r"CSR JWT request failed \(403\): Revoked."):
        request_c2pa_cert("gpi_1", "gpic_1", instance_pem, LEAF_PEM)


@pytest.mark.xfail(strict=True, reason="build_csr is to refuse an Ed25519 key as a bad argument.")
def test_build_csr_refuses_an_ed25519_key():
    with pytest.raises((ValueError, TypeError)):
        build_csr(generate_keypair(SigningAlgorithm.EDDSA)[0])
