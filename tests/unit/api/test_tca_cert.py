# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for api/tca/tca_utils.py — generic TCA certificate helpers."""

import base64
import datetime
from unittest.mock import MagicMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization.pkcs7 import (
    serialize_certificates,
)
from cryptography.x509.oid import NameOID

from trufo.api.tca.tca_utils import build_csr, est_enroll, extract_cert_chain

# --- Fixtures ---


@pytest.fixture
def es256_keypair():
    """Generate an in-memory ES256 private key and its PEM bytes."""
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return key, pem


def _self_signed_cert(private_key, cn="test", *, is_ca=False):
    """Build a self-signed cert for test fixtures."""
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1))
    )
    if is_ca:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
    return builder.sign(private_key, hashes.SHA256())


def _ca_issued_cert(subject_key, issuer_key, subject_cn, issuer_cn, *, is_ca=False):
    """Build a cert signed by issuer_key (not self-signed)."""
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject_cn)])
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_cn)])
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(subject_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1))
    )
    if is_ca:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=0), critical=True
        )
    return builder.sign(issuer_key, hashes.SHA256())


# --- build_csr tests ---


class TestBuildCsr:
    """build_csr creates a valid DER-encoded CSR."""

    def test_returns_der_bytes(self, es256_keypair):
        _, pem = es256_keypair
        der = build_csr(pem)
        assert isinstance(der, bytes)
        assert len(der) > 0

    def test_csr_is_parseable(self, es256_keypair):
        _, pem = es256_keypair
        der = build_csr(pem)
        csr = x509.load_der_x509_csr(der)
        assert csr.is_signature_valid

    def test_subject_is_placeholder(self, es256_keypair):
        _, pem = es256_keypair
        der = build_csr(pem)
        csr = x509.load_der_x509_csr(der)
        cn = csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        assert cn == "placeholder"

    def test_csr_public_key_matches_private(self, es256_keypair):
        key, pem = es256_keypair
        der = build_csr(pem)
        csr = x509.load_der_x509_csr(der)
        expected_pub = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        actual_pub = csr.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        assert actual_pub == expected_pub


# --- est_enroll tests ---


class TestEstEnroll:
    """est_enroll sends correct request to CA."""

    @patch("trufo.api.tca.tca_utils.requests.post")
    def test_returns_response_content_on_success(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            content=b"base64-pkcs7-data",
        )

        result = est_enroll("csr-jwt", b"csr-der", "c2pa-l1")

        assert result == b"base64-pkcs7-data"

    @patch("trufo.api.tca.tca_utils.requests.post")
    def test_sends_basic_auth_with_jwt(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, content=b"ok")

        est_enroll("my-jwt", b"csr", "c2pa-l1")

        call_kwargs = mock_post.call_args[1]
        expected_auth = base64.b64encode(b":my-jwt").decode()
        assert call_kwargs["headers"]["Authorization"] == f"Basic {expected_auth}"

    @patch("trufo.api.tca.tca_utils.requests.post")
    def test_url_includes_leaf_type(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, content=b"ok")

        est_enroll("jwt", b"csr", "c2pa-l1-test")

        url = mock_post.call_args[0][0]
        assert "/c2pa-l1-test/simpleenroll" in url

    @patch("trufo.api.tca.tca_utils.requests.post")
    def test_raises_on_failure(self, mock_post):
        resp = MagicMock(status_code=400, text="bad request")
        resp.json.return_value = {"detail": "invalid CSR"}
        mock_post.return_value = resp

        with pytest.raises(RuntimeError, match="EST enrollment failed"):
            est_enroll("jwt", b"csr", "c2pa-l1")


# --- extract_cert_chain tests ---


class TestExtractCertChain:
    """extract_cert_chain parses PKCS#7 into chain PEM."""

    def _build_pkcs7_b64(self, certs):
        """Serialize a list of x509.Certificate into base64 PKCS#7."""
        pkcs7_der = serialize_certificates(certs, serialization.Encoding.DER)
        return base64.b64encode(pkcs7_der)

    def test_chain_contains_leaf_and_intermediate_excluding_root(self):
        leaf_key = ec.generate_private_key(ec.SECP256R1())
        ica_key = ec.generate_private_key(ec.SECP256R1())
        root_key = ec.generate_private_key(ec.SECP256R1())
        root = _self_signed_cert(root_key, cn="root", is_ca=True)
        ica = _ca_issued_cert(ica_key, root_key, "ica", "root", is_ca=True)
        leaf = _ca_issued_cert(leaf_key, ica_key, "leaf", "ica", is_ca=False)

        pkcs7_b64 = self._build_pkcs7_b64([leaf, root, ica])
        chain_pem = extract_cert_chain(pkcs7_b64)

        assert chain_pem.startswith(b"-----BEGIN CERTIFICATE-----")
        # chain should contain leaf + intermediate (root excluded)
        assert chain_pem.count(b"-----BEGIN CERTIFICATE-----") == 2

    def test_chain_leaf_pem_is_parseable(self):
        key = ec.generate_private_key(ec.SECP256R1())
        cert = _self_signed_cert(key, cn="test-leaf")
        pkcs7_b64 = self._build_pkcs7_b64([cert])
        chain_pem = extract_cert_chain(pkcs7_b64)

        first_pem = (
            chain_pem.split(b"-----END CERTIFICATE-----\n", 1)[0] + b"-----END CERTIFICATE-----\n"
        )
        parsed = x509.load_pem_x509_certificate(first_pem)
        assert parsed.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "test-leaf"

    def test_empty_pkcs7_raises(self):
        # we need at least one cert for valid PKCS#7, so test with invalid data
        with pytest.raises(Exception):
            extract_cert_chain(base64.b64encode(b"not-valid-pkcs7"))

    def test_chain_ordered_issuing_ca_before_root_exclusion(self):
        """Chain is ordered as leaf, issuing CA; self-signed root is excluded."""
        root_key = ec.generate_private_key(ec.SECP256R1())
        ica_key = ec.generate_private_key(ec.SECP256R1())
        leaf_key = ec.generate_private_key(ec.SECP256R1())

        root = _self_signed_cert(root_key, cn="Root CA", is_ca=True)
        ica = _ca_issued_cert(ica_key, root_key, "Issuing CA", "Root CA", is_ca=True)
        leaf = _ca_issued_cert(leaf_key, ica_key, "Leaf", "Issuing CA")

        # PKCS#7 order is deliberately scrambled: root before issuing CA
        pkcs7_b64 = self._build_pkcs7_b64([leaf, root, ica])
        chain_pem = extract_cert_chain(pkcs7_b64)

        chain = x509.load_pem_x509_certificates(chain_pem)
        assert len(chain) == 2
        assert chain[0].subject == leaf.subject  # leaf first
        assert chain[1].subject == ica.subject  # issuing CA second
