# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Quickstart: procure a C2PA certificate from Trufo.

Part 1 — Test certificate (no account required).
Part 2 — Production certificate (requires account, OV, PV, subscription).

See docs/quickstart/1_c2pa_cert.md for prerequisites and explanations.
"""

from pathlib import Path

from trufo.crypto.algorithms import SigningAlgorithm
from trufo.crypto.keygen import generate_keypair

OUT_DIR = Path("certs")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Part 1 — Test Certificate
# ============================================================
# No account or API key needed.  Issued by Trufo's test CA — will not
# pass public validators, but the certificate format is identical to
# production.

from trufo.api.tca.certs_test import request_c2pa_test_cert

private_pem, _ = generate_keypair(SigningAlgorithm.ES256)

cert_chain_pem = request_c2pa_test_cert(
    org_name="My Company",
    common_name="My App",
    private_key_signer=private_pem,
)

key_path = OUT_DIR / "test_leaf_key.pem"
key_path.write_bytes(private_pem)
key_path.chmod(0o600)
(OUT_DIR / "test_cert_chain.pem").write_bytes(cert_chain_pem)

print(f"Test certificate saved to {OUT_DIR}/")


# ============================================================
# Part 2 — Production Certificate
# ============================================================
# Requires: account, OV approved, generator product with PV approved,
# active subscription, and an instance with a registered credential.

# -- one-time setup (run once per deployment environment) --

# from trufo.api.tca.certs_c2pa import create_instance, register_credential
# from trufo.util.credentials import load_session
#
# session = load_session()
#
# # Generate instance key — keep the private key secure
# instance_private_pem, instance_public_pem = generate_keypair(SigningAlgorithm.ES256)
#
# gpi_id = create_instance(session, gp_id="gp_...", name="Production server")
# gpic_id = register_credential(
#     session,
#     gpi_id=gpi_id,
#     label="prod-key-1",
#     key_algorithm="ES256",
#     public_key_pem=instance_public_pem.decode(),
# )
# # Persist gpi_id, gpic_id, and instance_private_pem securely

# -- enrollment (run on each certificate renewal) --

# from trufo.api.tca.certs_c2pa import request_c2pa_cert
# from trufo.api.tca.tca_utils import LeafType
#
# leaf_private_pem, _ = generate_keypair(SigningAlgorithm.ES256)
#
# cert_chain_pem = request_c2pa_cert(
#     gpi_id=gpi_id,
#     gpic_id=gpic_id,
#     instance_key_pem=instance_private_pem,
#     private_key_signer=leaf_private_pem,
#     leaf_type=LeafType.C2PA_L1,
#     validity_days=90,
# )
#
# key_path = OUT_DIR / "leaf_key.pem"
# key_path.write_bytes(leaf_private_pem)
# key_path.chmod(0o600)
# (OUT_DIR / "cert_chain.pem").write_bytes(cert_chain_pem)
#
# print(f"Production certificate saved to {OUT_DIR}/")
