# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""User-facing C2PA AI system types supported by Trufo."""

from enum import Enum


class AIInvolvement(str, Enum):
    """User-facing AI involvement type."""

    # the AI system generated the content
    AI_GENERATED = "ai_generated"
    # the AI system modified existing content
    AI_MODIFIED = "ai_modified"

    @staticmethod
    def validate(ai_involvement: str) -> "AIInvolvement":
        return AIInvolvement(ai_involvement)
