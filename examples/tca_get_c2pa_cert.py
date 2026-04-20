# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Example: obtain a C2PA test certificate from the Trufo CA.

Generates an ES256 key pair and enrolls for a C2PA L1 test certificate
via the TCA test EST flow.  No account authentication required.

Outputs::

    leaf_key.pem    — leaf private key (keep secure)
    cert_chain.pem  — leaf + intermediate certificates (PEM)

For production enrollment, use the full RA pipeline instead —
see ``trufo.api.tca.certs_c2pa.request_c2pa_cert``.
"""

from pathlib import Path

from trufo.api.tca.certs_test import request_c2pa_test_cert
from trufo.crypto.algorithms import SigningAlgorithm
from trufo.crypto.keygen import generate_keypair

# --- configuration ---

ORG_NAME = "My Company"
COMMON_NAME = "My App"
OUT_DIR = Path("certs")

# --- generate key pair ---

private_pem, _public_pem = generate_keypair(SigningAlgorithm.ES256)

# --- enroll for test certificate ---

cert_chain_pem = request_c2pa_test_cert(
    org_name=ORG_NAME,
    common_name=COMMON_NAME,
    private_key_signer=private_pem,
)

# --- write outputs ---

OUT_DIR.mkdir(parents=True, exist_ok=True)

key_path = OUT_DIR / "leaf_key.pem"
key_path.write_bytes(private_pem)
key_path.chmod(0o600)

chain_path = OUT_DIR / "cert_chain.pem"
chain_path.write_bytes(cert_chain_pem)

print(f"Leaf key:    {key_path}")
print(f"Cert chain:  {chain_path}")
