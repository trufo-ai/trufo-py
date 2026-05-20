# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""User-facing C2PA action types supported by Trufo."""

from enum import Enum


class TrufoAction(str, Enum):
    """User-facing C2PA action type."""

    TRANSCODE = "transcode"
    REPACKAGE = "repackage"
    WATERMARK = "watermark"
    PUBLISH = "publish"