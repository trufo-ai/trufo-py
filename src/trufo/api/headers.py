# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Standard request headers sent on every Trufo API call.

The version headers are self-reported telemetry, not authentication: the server
records them when present and ignores them when absent, so calling the API
directly without them works exactly the same. They let Trufo see which SDK
generations are in use — which endpoints, which auth flows — without changing
any API contract.

The one place versions are *enforced* is the distributed signing path, which
requires a minimum trufo-py / trufo-provenance release. That check lives
server-side and predates this module.
"""

from typing import Optional

TF_VERSION_HEADER = "X-TF-Version"
TFP_VERSION_HEADER = "X-TFP-Version"


def sdk_headers(api_key: Optional[str] = None, **extra: str) -> dict[str, str]:
    """Build the standard header set for a Trufo API request.

    Args:
        api_key: Sent as ``X-API-Key`` when provided.
        **extra: Additional headers, merged last so callers can override.

    Returns:
        Header dict carrying the SDK version, the API key if given, and any
        extras. The trufo-provenance version is included only when that package
        is installed.
    """
    from trufo import __version__

    headers: dict[str, str] = {TF_VERSION_HEADER: __version__}

    tfp_version = _tfp_version()
    if tfp_version is not None:
        headers[TFP_VERSION_HEADER] = tfp_version

    if api_key is not None:
        headers["X-API-Key"] = api_key

    headers.update(extra)
    return headers


def _tfp_version() -> Optional[str]:
    """Return the installed trufo-provenance version, or None if absent."""
    try:
        from tfprov import __version__ as tfp_version

        return tfp_version
    except ImportError:
        return None
