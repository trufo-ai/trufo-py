# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""User-facing C2PA watermark types supported by Trufo."""

from enum import Enum


class WatermarkEffort(str, Enum):
    """Failure tolerance of an explicit watermark request.

    Watermarking is off by default; a ``["watermark", {...}]`` action requests
    it, and ``effort`` sets what happens when it cannot be applied. A bare
    watermark action defaults to ``REQUIRE``.
    """

    # any failure (unsupported format or runtime) fails the sign
    REQUIRE = "require"
    # an unsupported format is skipped with a warning; a runtime failure on a
    # supported format fails the sign
    REQUIRE_IF_SUPPORTED = "require_if_supported"
    # any failure is skipped with a warning
    BEST_EFFORT = "best_effort"
