"""Enums shared by TPS helper modules."""

import enum


class DefaultCawgIdentityId(str, enum.Enum):
    """
    CAWG identity IDs for standard-behavior use in the `cawg_identity` assertion.
    """

    TEST = "test"
    ORG_INTERIM = "org_interim"
