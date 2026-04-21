# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
C2PA signing helpers for the Trufo TPS.
"""

import base64

import requests

from trufo.api.endpoints import TRUFO_API_URL, TPS_C2PA_SIGN_TEST


def sign_c2pa_test(
    api_key: str,
    media_bytes: bytes,
    actions: list | None = None,
    assertions: list | None = None,
) -> bytes:
    """Sign a media file with C2PA via the TPS test endpoint.

    Args:
        api_key: TPS API key (``X-API-Key`` header).
        media_bytes: Raw bytes of the media file to sign.
        actions: Ordered list of ``[action_name, params]`` pairs (default ``[]``).
        assertions: List of ``[assertion_name, params]`` pairs (default ``[]``).
            If provided, ``"cawg_identity"`` must be one of the entries.

    Returns:
        Signed media bytes.

    Raises:
        ValueError: If ``assertions`` is provided without a ``"cawg_identity"`` entry.
        requests.HTTPError: If the API returns a non-2xx response.
    """
    if assertions and not any(a[0] == "cawg_identity" for a in assertions):
        raise ValueError("'cawg_identity' is required when assertions are provided")

    body = {
        "media_input": base64.b64encode(media_bytes).decode(),
        "actions": actions or [],
        "assertions": assertions or [],
    }

    resp = requests.post(
        TRUFO_API_URL + TPS_C2PA_SIGN_TEST,
        json=body,
        headers={"X-API-Key": api_key},
        timeout=60,
    )
    resp.raise_for_status()

    return base64.b64decode(resp.json()["media_output"])
