# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""User-facing C2PA assertion labels that may be redacted."""

from enum import Enum


class RedactableAssertion(str, Enum):
    """User-facing assertion label supported for redaction.

    A small, deliberately closed set — start with what's tested, extend as
    more labels are verified safe to redact. Each entry may be suffixed with
    ``__N`` (e.g. ``"c2pa.metadata__1"``) to target one specific
    disambiguated instance when a manifest carries more than one assertion
    under the same base label.
    """

    METADATA = "c2pa.metadata"


class RedactionReason(str, Enum):
    """Rationale for a redaction, recorded on the resulting ``c2pa.redacted``
    action (C2PA spec §18.15.4.2). Applies to every label in a given
    ``redactions`` list."""

    PII_PRESENT = "c2pa.PII.present"
    INVALID_DATA = "c2pa.invalid.data"
    TRADE_SECRET_PRESENT = "c2pa.trade-secret.present"
    GOVERNMENT_CONFIDENTIAL = "c2pa.government.confidential"
