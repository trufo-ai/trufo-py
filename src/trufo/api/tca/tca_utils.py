# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Generic TCA certificate enrollment helpers.

Shared infrastructure for certificate enrollment via any Trufo CA
EST endpoint (RFC 7030): CSR construction, EST submission, and
PKCS#7 response parsing.
"""

import base64
from enum import Enum
from pathlib import Path

import requests
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization.pkcs7 import load_der_pkcs7_certificates
from cryptography.x509.oid import NameOID

from trufo.api.auth import extract_detail
from trufo.api.endpoints import TRUFO_CA_URL
from trufo.crypto.algorithms import ALG_TO_HASH, SigningAlgorithm, infer_signing_algorithm


class LeafType(str, Enum):
    """Certificate leaf types accepted by the Trufo CA."""

    C2PA_L1 = "c2pa-l1"
    C2PA_L2 = "c2pa-l2"
    C2PA_L1_TEST = "c2pa-l1-test"
    C2PA_L2_TEST = "c2pa-l2-test"
    CTSA = "ctsa"
    CTSA_TEST = "ctsa-test"
    CAWG_INTERIM = "cawg-interim"
    CAWG_INTERIM_TEST = "cawg-interim-test"


TEST_HMAC_SECRET = "hello-trufo"


def _infer_algorithm_from_ec_key(
    private_key: ec.EllipticCurvePrivateKey,
) -> SigningAlgorithm:
    """Infer JWA signing algorithm from an EC private key object."""
    pub_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return infer_signing_algorithm(pub_pem)


def build_csr(private_key_signer: str | Path | bytes | ec.EllipticCurvePrivateKey) -> bytes:
    """Build a PKCS#10 CSR signed by the leaf private key.

    The CSR subject DN is a placeholder — the CA uses the DN from the
    CSR JWT.  The CSR proves the requester holds the leaf private key.

    Args:
        private_key_signer: Leaf private key.  Accepts PEM bytes,
            a filesystem path (``str`` or ``Path``) to a PEM file,
            or an ``ec.EllipticCurvePrivateKey`` instance
            (e.g. an AWS KMS adapter).

    Returns:
        DER-encoded CSR bytes.

    Raises:
        TypeError: If *private_key_signer* is not a supported type.
        ValueError: If the EC curve is unsupported.
    """
    private_key = None
    if isinstance(private_key_signer, str):
        private_key_signer = Path(private_key_signer)
    if isinstance(private_key_signer, Path):
        private_key_signer = private_key_signer.read_bytes()
    if isinstance(private_key_signer, bytes):
        private_key = serialization.load_pem_private_key(private_key_signer, password=None)
    if isinstance(private_key_signer, ec.EllipticCurvePrivateKey):
        private_key = private_key_signer
    if private_key is None:
        raise TypeError(f"Unsupported private_key_signer type: {type(private_key_signer)!r}")

    signing_algorithm = _infer_algorithm_from_ec_key(private_key)
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "placeholder")]))
        .sign(private_key, ALG_TO_HASH[signing_algorithm])
    )
    return csr.public_bytes(serialization.Encoding.DER)


def est_enroll(csr_jwt: str, csr_der: bytes, leaf_type_value: str) -> bytes:
    """Submit a CSR to the CA via EST simpleenroll (RFC 7030).

    The CSR JWT is sent as the HTTP Basic auth password (username is
    empty).

    Args:
        csr_jwt: Signed CSR JWT (from RA or test HMAC).
        csr_der: DER-encoded PKCS#10 CSR.
        leaf_type_value: Leaf type string (e.g. ``"c2pa-l1"``).

    Returns:
        Raw response body (base64-encoded PKCS#7).

    Raises:
        RuntimeError: If the CA returns a non-200 status.
    """
    auth_value = base64.b64encode(f":{csr_jwt}".encode()).decode()
    csr_b64 = base64.b64encode(csr_der).decode()

    resp = requests.post(
        f"{TRUFO_CA_URL}/.well-known/est/{leaf_type_value}/simpleenroll",
        headers={
            "Content-Type": "application/pkcs10",
            "Authorization": f"Basic {auth_value}",
        },
        data=csr_b64,
        timeout=30,
    )
    if resp.status_code != 200:
        detail = extract_detail(resp)
        raise RuntimeError(f"EST enrollment failed ({resp.status_code}): {detail}")

    return resp.content


def extract_cert_chain(pkcs7_b64: bytes) -> bytes:
    """Extract a PEM certificate chain from a base64-encoded PKCS#7 response.

    The leaf certificate is identified as the first cert without
    ``BasicConstraints ca=True``.  Self-signed root certificates are
    excluded per the C2PA specification.

    Args:
        pkcs7_b64: Base64-encoded DER PKCS#7 (as returned by
            :func:`est_enroll`).

    Returns:
        PEM bytes containing the leaf certificate followed by any
        intermediate CA certificates.

    Raises:
        RuntimeError: If the PKCS#7 container is empty.
    """
    pkcs7_der = base64.b64decode(pkcs7_b64)
    certs = load_der_pkcs7_certificates(pkcs7_der)

    if not certs:
        raise RuntimeError("PKCS#7 response contained no certificates.")

    leaf_cert = None
    ca_certs = []
    for cert in certs:
        try:
            bc = cert.extensions.get_extension_for_class(x509.BasicConstraints)
            if bc.value.ca:
                ca_certs.append(cert)
                continue
        except x509.ExtensionNotFound:
            pass
        if leaf_cert is None:
            leaf_cert = cert
        else:
            ca_certs.append(cert)

    if leaf_cert is None:
        leaf_cert = certs[0]
        ca_certs = certs[1:]

    # order CA certs: walk from leaf's issuer to self-signed root
    ca_certs = _order_ca_chain(leaf_cert, ca_certs)

    leaf_pem = leaf_cert.public_bytes(serialization.Encoding.PEM)
    cert_chain_pem = leaf_pem
    for ca_cert in ca_certs:
        if ca_cert.subject == ca_cert.issuer:
            continue  # exclude self-signed root per C2PA spec
        cert_chain_pem += ca_cert.public_bytes(serialization.Encoding.PEM)

    return cert_chain_pem


def _order_ca_chain(
    leaf: x509.Certificate,
    ca_certs: list[x509.Certificate],
) -> list[x509.Certificate]:
    """Order CA certificates from the issuing CA toward the root.

    Walks the issuer chain starting from *leaf*'s issuer.  Certificates
    not reachable in the chain are appended at the end (defensive).

    Args:
        leaf: The leaf (end-entity) certificate.
        ca_certs: Unordered list of CA certificates from the PKCS#7.

    Returns:
        CA certificates ordered issuing-CA-first, root-last.
    """
    by_subject = {cert.subject: cert for cert in ca_certs}
    ordered: list[x509.Certificate] = []
    current_issuer = leaf.issuer

    while current_issuer in by_subject:
        cert = by_subject.pop(current_issuer)
        ordered.append(cert)
        if cert.subject == cert.issuer:
            break  # self-signed root
        current_issuer = cert.issuer

    # append any unreachable certs (shouldn't happen with well-formed PKCS#7)
    ordered.extend(by_subject.values())
    return ordered
