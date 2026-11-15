# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""User-facing C2PA assertion types supported by Trufo."""

from enum import Enum


class UserAssertion(str, Enum):
    """User-facing C2PA assertion type."""

    # TODO(sunset-2027-01-31): the 'ai_disclosure' entry goes; successor UserAssertion.AI_SYSTEM
    AI_DISCLOSURE = "ai_disclosure"
    AI_SYSTEM = "ai_system"
    C2PA_METADATA = "c2pa_metadata"
    CAWG_IDENTITY = "cawg_identity"
    CAWG_METADATA = "cawg_metadata"
    CAWG_TRAINING = "cawg_training"
    CUSTOM = "custom"
    CREATION = "creation"
    INGREDIENT = "ingredient"
