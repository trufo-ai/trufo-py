# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Public settings for C2PA manifest construction."""

import re
from dataclasses import dataclass
from enum import Enum

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


# the hosts Trufo fetches a remote C2PA manifest from unless the caller names others
DEFAULT_REMOTE_MANIFEST_HOSTS: tuple[str, ...] = ("cai-manifests.adobe.com",)

# an exact DNS host name: lowercase ASCII labels, at least two, the last starting with a letter
_HOST_NAME = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z"
)


@dataclass(frozen=True)
class RemoteManifestSettings:
    """Whether, and from which hosts, Trufo fetches a C2PA manifest that a file references by URL.

    A file can carry its manifest's URL, in its XMP ``dcterms:provenance``, in place of the
    manifest. Signing in Local mode fetches that manifest over HTTPS when its host is one of
    ``allowed_hosts``, which tells that host that the file is being signed and from which
    address. Each entry is an exact host name, with no scheme, port, path or wildcard.
    """

    fetch: bool = True
    # stored as a tuple of lowercase names
    allowed_hosts: list[str] | tuple[str, ...] = DEFAULT_REMOTE_MANIFEST_HOSTS

    def __post_init__(self) -> None:
        if not isinstance(self.fetch, bool):
            raise TypeError("fetch must be bool.")
        hosts = self.allowed_hosts
        if not isinstance(hosts, (list, tuple)) or not all(isinstance(h, str) for h in hosts):
            raise TypeError("allowed_hosts must be a list of host names.")
        hosts = tuple(host.lower() for host in hosts)
        for host in hosts:
            if _HOST_NAME.match(host) is None:
                raise ValueError(
                    f"allowed_hosts entry {host!r} is not an exact host name such as "
                    "'manifests.example.com'."
                )
        object.__setattr__(self, "allowed_hosts", hosts)


class SignedInputPolicy(str, Enum):
    """What Trufo does when the input file already carries a C2PA manifest."""

    # the input's manifest becomes the parentOf ingredient
    KEEP = "keep"
    # Trufo's best practice; the default when no policy is sent
    AUTO = "auto"

    @staticmethod
    def validate(policy: str) -> "SignedInputPolicy":
        return SignedInputPolicy(policy)


class SignedIngredientPolicy(str, Enum):
    """What Trufo does when an ingredient's media already carries a C2PA manifest."""

    # the media's manifest is kept with the ingredient
    KEEP = "keep"
    # Trufo's best practice; the default when no policy is sent
    AUTO = "auto"

    @staticmethod
    def validate(policy: str) -> "SignedIngredientPolicy":
        return SignedIngredientPolicy(policy)
