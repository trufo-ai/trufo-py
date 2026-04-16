# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""AWS service helpers for KMS signing operations."""

import boto3
import botocore.client


def create_aws_kms_client(
    region: str,
    access_key: str | None,
    secret_key: str | None,
    profile: str | None,
) -> botocore.client.BaseClient:
    """Create a boto3 KMS client using a credential resolution chain.

    Resolution order:
        1. Explicit access_key + secret_key
        2. Named profile
        3. Default boto3 chain (IAM role, env vars, instance metadata)

    Args:
        region: AWS region name (e.g. "us-east-1").
        access_key: AWS access key ID, or None.
        secret_key: AWS secret access key, or None.
        profile: AWS profile name, or None.

    Returns:
        A boto3 KMS client instance.
    """
    if access_key and secret_key:
        return boto3.client(
            "kms",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    if profile:
        session = boto3.Session(profile_name=profile, region_name=region)
        return session.client("kms")

    return boto3.client("kms", region_name=region)


# map KMS key spec to (jwa_algorithm_name, kms_signing_algorithm)
AWS_KEY_SPEC_MAP = {
    "ECC_NIST_P256": ("ES256", "ECDSA_SHA_256"),
    "ECC_NIST_P384": ("ES384", "ECDSA_SHA_384"),
}


def aws_key_spec_map(key_spec: str) -> tuple[str, str]:
    """Map an AWS KMS key spec to JWA and KMS signing algorithm names.

    Args:
        key_spec: AWS KMS key specification string (e.g. "ECC_NIST_P256").

    Returns:
        Tuple of (jwa_algorithm_name, kms_signing_algorithm).

    Raises:
        ValueError: If the key spec is not supported.
    """
    if key_spec not in AWS_KEY_SPEC_MAP:
        raise ValueError(
            f"Unsupported KMS key spec: {key_spec}. "
            f"Supported: {', '.join(AWS_KEY_SPEC_MAP.keys())}"
        )

    return AWS_KEY_SPEC_MAP[key_spec]
