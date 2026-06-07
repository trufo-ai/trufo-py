# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Public enum contracts: exact members/values and str-mixin expectations.

These enums are duplicated across repos (tfprov keeps its own copies); this
pins trufo-py's side so any value drift or accidental base-class change fails
locally without needing tfprov installed.
"""

import pytest

from trufo.c2pa.actions import TrufoAction
from trufo.c2pa.assertions import UserAssertion
from trufo.crypt.algorithms import LeafType, SigningAlgorithm

# String-keyed public enums: the member value IS the wire/API string, so each
# must be a str-mixin enum (compares and serializes as the bare string).
STR_ENUMS = {
    UserAssertion: {
        "AI_DISCLOSURE": "ai_disclosure",
        "CAWG_IDENTITY": "cawg_identity",
        "CAWG_METADATA": "cawg_metadata",
        "CAWG_TRAINING": "cawg_training",
        "CUSTOM": "custom",
    },
    TrufoAction: {
        "TRANSCODE": "transcode",
        "REPACKAGE": "repackage",
        "WATERMARK": "watermark",
        "PUBLISH": "publish",
    },
    LeafType: {
        "C2PA_L1": "c2pa-l1",
        "C2PA_L2": "c2pa-l2",
        "C2PA_L1_TEST": "c2pa-l1-test",
        "C2PA_L2_TEST": "c2pa-l2-test",
        "CTSA": "ctsa",
        "CTSA_TEST": "ctsa-test",
        "CAWG_INTERIM": "cawg-interim",
        "CAWG_INTERIM_TEST": "cawg-interim-test",
    },
}


@pytest.mark.parametrize(
    "enum_cls, expected",
    list(STR_ENUMS.items()),
    ids=[cls.__name__ for cls in STR_ENUMS],
)
def test_str_enum_members_values_and_type(enum_cls, expected):
    """Exact member set + values, and str-mixin so a member == its wire string."""
    assert issubclass(enum_cls, str)
    assert {m.name: m.value for m in enum_cls} == expected
    for name, value in expected.items():
        assert enum_cls[name] == value


def test_signing_algorithm_is_structured_not_str():
    """SigningAlgorithm carries (alg_name, hash_alg); it is intentionally a
    plain Enum, not a str-mixin (its values are tuples)."""
    assert not issubclass(SigningAlgorithm, str)
    expected = {
        "ES256": ("ES256", "SHA256"),
        "ES384": ("ES384", "SHA384"),
        "ES512": ("ES512", "SHA512"),
        "EDDSA": ("EdDSA", None),
    }
    assert {m.name: m.value for m in SigningAlgorithm} == expected
    for name, (alg_name, hash_alg) in expected.items():
        member = SigningAlgorithm[name]
        assert member.alg_name == alg_name
        assert member.hash_alg == hash_alg
