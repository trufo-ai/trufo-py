# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Public settings for C2PA manifest construction."""

from dataclasses import dataclass

from trufo.c2pa.thumbnails import ThumbnailSettings


@dataclass(frozen=True)
class ManifestSettings:
    """Settings applied while constructing the active C2PA manifest."""

    manifest_title: str | None = None
    ingredient_title: str | None = None
    thumbnail_settings: ThumbnailSettings | None = None
    all_actions_included: bool | None = None

    def __post_init__(self) -> None:
        for name in ("manifest_title", "ingredient_title"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"{name} must be a non-empty string or None.")
        if self.thumbnail_settings is not None and not isinstance(
            self.thumbnail_settings, ThumbnailSettings
        ):
            raise TypeError("thumbnail_settings must be ThumbnailSettings or None.")
        if self.all_actions_included is not None and not isinstance(
            self.all_actions_included, bool
        ):
            raise TypeError("all_actions_included must be bool or None.")
