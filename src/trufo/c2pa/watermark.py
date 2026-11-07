# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""User-facing C2PA watermark types supported by Trufo."""

import re
from dataclasses import dataclass
from enum import Enum


class WatermarkProfile(str, Enum):
    """Local watermark embedding profile."""

    DEFAULT = "default"
    FAST = "fast"


@dataclass(frozen=True)
class WatermarkSettings:
    """Local watermark execution settings, separate from the watermark action.

    ``profile`` accepts ``"default"`` or ``"fast"``. Fast requests best-effort
    video acceleration; GPU acceleration requires NVIDIA CUDA.
    ``device=None`` chooses CUDA when available, otherwise CPU; ``"cpu"``
    forces CPU, ``"cuda"`` uses the current visible GPU, and ``"cuda:N"``
    selects visible GPU index N (a canonical nonnegative decimal integer).
    An unavailable explicit CUDA selection raises ValueError at execution.
    These settings do not request watermarking or enter the C2PA manifest.
    """

    profile: WatermarkProfile = WatermarkProfile.DEFAULT
    device: str | None = None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "profile", WatermarkProfile(self.profile))
        except (TypeError, ValueError) as exc:
            raise ValueError("Watermark profile must be 'default' or 'fast'.") from exc
        if self.device is not None and (
            not isinstance(self.device, str)
            or re.fullmatch(r"cpu|cuda(?::(?:0|[1-9][0-9]*))?", self.device) is None
        ):
            raise ValueError("Watermark device must be None, 'cpu', 'cuda', or 'cuda:N'.")


class WatermarkEffort(str, Enum):
    """Failure tolerance of an explicit watermark request.

    Watermarking is off by default; a ``["watermark", {...}]`` action requests
    it, and ``effort_policy`` sets what happens when it cannot be applied. A
    bare watermark action defaults to ``REQUIRE``.
    """

    # any failure (unsupported format or runtime) fails the sign
    REQUIRE = "require"
    # an unsupported format is skipped with a warning; a runtime failure on a
    # supported format fails the sign
    REQUIRE_IF_SUPPORTED = "require_if_supported"
    # any failure is skipped with a warning
    BEST_EFFORT = "best_effort"


class WatermarkIDAllocationMode(str, Enum):
    """How the embedded watermark ID is allocated.

    A watermark action's ``wid_allocation_mode`` selects it. A bare watermark
    action defaults to ``PER_EMBED``.
    """

    # a new watermark ID for this embed
    PER_EMBED = "per_embed"
    # the watermark ID of a registered AI system for the request's AI involvement
    PER_AI_SYSTEM = "per_ai_system"
    # reserved; requesting this mode raises NotImplementedError
    PER_ASSET = "per_asset"

    @staticmethod
    def validate(mode: str) -> "WatermarkIDAllocationMode":
        selected = WatermarkIDAllocationMode(mode)
        if selected == WatermarkIDAllocationMode.PER_ASSET:
            raise NotImplementedError("Per-asset watermark ID allocation is not supported.")
        return selected


# TODO(sunset-2027-01-31): WatermarkMode and the watermark 'mode' parameter go;
# successor WatermarkIDAllocationMode
class WatermarkMode(str, Enum):
    """Deprecated: use WatermarkIDAllocationMode.

    What the embedded watermark ID resolves to. A watermark action's ``mode``
    selects the kind of mark; ``WatermarkIDAllocationMode.PER_EMBED`` replaces
    ``PROVENANCE``.
    """

    # a per-content mark linked to this signing record
    PROVENANCE = "provenance"
    # reserved; requesting this mode raises NotImplementedError
    COMPLIANCE = "compliance"

    @staticmethod
    def validate(mode: str) -> None:
        """Reject unsupported modes before sending a request or invoking the engine."""
        try:
            selected = WatermarkMode(mode)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid watermark mode.") from exc
        if selected == WatermarkMode.COMPLIANCE:
            raise NotImplementedError("Compliance watermarking is not supported.")
