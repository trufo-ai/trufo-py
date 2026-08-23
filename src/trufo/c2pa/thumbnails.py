# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Public thumbnail settings for C2PA signing."""

from dataclasses import dataclass
from enum import Enum


class ThumbnailPolicy(str, Enum):
    """Which C2PA thumbnails Trufo should generate."""

    AUTO = "auto"
    NONE = "none"
    AUTO_NO_INGREDIENT = "auto_no_ingredient"


class ThumbnailSize(str, Enum):
    """Thumbnail encoding preset."""

    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ThumbnailSettings:
    """Thumbnail generation policy and encoding size."""

    policy: ThumbnailPolicy = ThumbnailPolicy.AUTO
    size: ThumbnailSize = ThumbnailSize.MEDIUM

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "policy", ThumbnailPolicy(self.policy))
            object.__setattr__(self, "size", ThumbnailSize(self.size))
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid C2PA thumbnail settings.") from exc
