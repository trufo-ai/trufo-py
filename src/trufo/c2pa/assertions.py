# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""User-facing C2PA assertion types supported by Trufo."""

from enum import Enum


class UserAssertion(str, Enum):
    """User-facing C2PA assertion type."""

    AI_DISCLOSURE = "ai_disclosure"
    CAWG_IDENTITY = "cawg_identity"
    CAWG_METADATA = "cawg_metadata"
    CAWG_TRAINING = "cawg_training"