# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""User-facing C2PA redaction types supported by Trufo."""

from enum import Enum


class RedactableAssertion(str, Enum):
    """User-facing C2PA assertion label that may be redacted."""

    METADATA = "c2pa.metadata"
    CAWG_METADATA = "cawg.metadata"
    CAWG_TRAINING_MINING = "cawg.training-mining"
    CAWG_IDENTITY = "cawg.identity"


class RedactionReason(str, Enum):
    """User-facing rationale recorded on the resulting c2pa.redacted action."""

    PII_PRESENT = "c2pa.PII.present"
    INVALID_DATA = "c2pa.invalid.data"
    TRADE_SECRET_PRESENT = "c2pa.trade-secret.present"
    GOVERNMENT_CONFIDENTIAL = "c2pa.government.confidential"
