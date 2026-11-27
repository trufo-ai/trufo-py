# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Public value types and the enums whose values go on the wire.

The shared C2PA enums are owned by this package and imported by the engine; these checks run
without it.
"""

import re

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from trufo import ExecutionMode, TaskStatus, TaskType
from trufo.c2pa import (
    DEFAULT_REMOTE_MANIFEST_HOSTS,
    AIInvolvement,
    DigitalSourceType,
    ManifestSettings,
    RedactableAssertion,
    RedactionReason,
    RemoteManifestSettings,
    SignedIngredientPolicy,
    SignedInputPolicy,
    ThumbnailPolicy,
    ThumbnailSettings,
    ThumbnailSize,
    TrufoAction,
    UserAssertion,
    WatermarkEffort,
    WatermarkIDAllocationMode,
    WatermarkMode,
    WatermarkProfile,
    WatermarkSettings,
)
from trufo.crypt.algorithms import ALG_TO_CURVE, ALG_TO_HASH, LeafType, SigningAlgorithm
from trufo.util.credentials import TrufoAPIKey

_IPTC = "http://cv.iptc.org/newscodes/digitalsourcetype/"


@pytest.mark.parametrize(
    "host",
    [
        "https://example.com",  # a scheme
        "example.com:443",  # a port
        "example.com/manifests",  # a path
        "user@example.com",  # userinfo
        "*.example.com",  # a wildcard
        "192.0.2.1",  # an IPv4 address
        "[2001:db8::1]",  # an IPv6 address
        "localhost",  # no dot
        "example.com.",  # a trailing dot
        "exa mple.com",  # whitespace
        "bücher.example",  # not ASCII; an internationalized name is given in its xn-- form
        "-a.example.com",  # a label that starts with a hyphen
        "a" * 64 + ".example.com",  # a label over 63 characters
        "",
    ],
)
def test_remote_manifest_hosts_are_exact_names(host):
    with pytest.raises(ValueError, match="allowed_hosts"):
        RemoteManifestSettings(allowed_hosts=[host])


def test_remote_manifest_defaults():
    settings = RemoteManifestSettings()
    assert settings.fetch is True
    assert settings.allowed_hosts == DEFAULT_REMOTE_MANIFEST_HOSTS == ("cai-manifests.adobe.com",)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        (
            {"allowed_hosts": ["Manifests.Example.com", "a.b-c.example"]},
            ("manifests.example.com", "a.b-c.example"),
        ),
        ({"allowed_hosts": ("manifests.example.com",)}, ("manifests.example.com",)),
        ({"allowed_hosts": []}, ()),
        ({"allowed_hosts": "example.com"}, TypeError),
        ({"allowed_hosts": [b"example.com"]}, TypeError),
        ({"allowed_hosts": None}, TypeError),
        ({"allowed_hosts": [None]}, TypeError),
        ({"fetch": "no"}, TypeError),
    ],
)
def test_remote_manifest_settings_shape(kwargs, expected):
    if expected is TypeError:
        with pytest.raises(TypeError, match=next(iter(kwargs))):
            RemoteManifestSettings(**kwargs)
    else:
        assert RemoteManifestSettings(**kwargs).allowed_hosts == expected


# a member's value is its wire string, and a str enum compares equal to it
_WIRE_ENUMS = {
    UserAssertion: {
        "AI_DISCLOSURE": "ai_disclosure",
        "AI_SYSTEM": "ai_system",
        "C2PA_METADATA": "c2pa_metadata",
        "CAWG_IDENTITY": "cawg_identity",
        "CAWG_METADATA": "cawg_metadata",
        "CAWG_TRAINING": "cawg_training",
        "CUSTOM": "custom",
        "CREATION": "creation",
        "INGREDIENT": "ingredient",
    },
    AIInvolvement: {"AI_GENERATED": "ai_generated", "AI_MODIFIED": "ai_modified"},
    SignedIngredientPolicy: {"KEEP": "keep", "AUTO": "auto"},
    SignedInputPolicy: {"KEEP": "keep", "AUTO": "auto"},
    TrufoAction: {
        "RESIZE": "resize",
        "CROP": "crop",
        "TRIM": "trim",
        "TRANSCODE": "transcode",
        "REPACKAGE": "repackage",
        "WATERMARK": "watermark",
        "PUBLISH": "publish",
        "REDACT": "redact",
    },
    WatermarkEffort: {
        "REQUIRE": "require",
        "REQUIRE_IF_SUPPORTED": "require_if_supported",
        "BEST_EFFORT": "best_effort",
    },
    WatermarkIDAllocationMode: {
        "PER_EMBED": "per_embed",
        "PER_AI_SYSTEM": "per_ai_system",
        "PER_ASSET": "per_asset",
    },
    WatermarkMode: {"PROVENANCE": "provenance", "COMPLIANCE": "compliance"},
    TrufoAPIKey: {
        "TRUFO_API": "trufo-api",
        "C2PA_SIGN_PROD": "c2pa-sign-prod",
        "C2PA_SIGN_TEST": "c2pa-sign-test",
        "CONTENT_RECOVER_TEST": "content-recover-test",
        "CONTENT_RECOVER_PROD": "content-recover-prod",
        "WATERMARK_TEST": "watermark-test",
        "WATERMARK_PROD": "watermark-prod",
        "TSA": "tsa",
    },
    LeafType: {
        "C2PA_L1": "c2pa-l1",
        "C2PA_L2": "c2pa-l2",
        "C2PA_L1_DUMMY": "c2pa-l1-test",
        "C2PA_L2_DUMMY": "c2pa-l2-test",
        "CTSA": "ctsa",
        "CTSA_TEST": "ctsa-test",
        "CAWG_INTERIM": "cawg-interim",
        "CAWG_INTERIM_DUMMY": "cawg-interim-test",
    },
    DigitalSourceType: {
        **{
            "_".join(word.upper() for word in re.findall("[A-Z]?[a-z]+", term)): _IPTC + term
            for term in (
                "digitalCapture computationalCapture compositeCapture screenCapture negativeFilm "
                "positiveFilm print digitalCreation algorithmicMedia dataDrivenMedia humanEdits "
                "algorithmicallyEnhanced composite compositeSynthetic trainedAlgorithmicMedia "
                "virtualRecording compositeWithTrainedAlgorithmicMedia digitalArt"
            ).split()
        },
        "EMPTY": "http://c2pa.org/digitalsourcetype/empty",
        "TRAINED_ALGORITHMIC_DATA": "http://c2pa.org/digitalsourcetype/trainedAlgorithmicData",
    },
    RedactableAssertion: {
        "C2PA_METADATA": "c2pa.metadata",
        "CAWG_METADATA": "cawg.metadata",
        "CAWG_TRAINING_MINING": "cawg.training-mining",
        "CAWG_IDENTITY": "cawg.identity",
    },
    RedactionReason: {
        "PII_PRESENT": "c2pa.PII.present",
        "INVALID_DATA": "c2pa.invalid.data",
        "TRADE_SECRET_PRESENT": "c2pa.trade-secret.present",
        "GOVERNMENT_CONFIDENTIAL": "c2pa.government.confidential",
    },
    # members whose value is their name in lowercase
    **{
        enum_cls: {name: name.lower() for name in names.split()}
        for enum_cls, names in {
            ThumbnailPolicy: "AUTO NONE AUTO_NO_INGREDIENT",
            ThumbnailSize: "MEDIUM HIGH",
            WatermarkProfile: "DEFAULT FAST",
            ExecutionMode: "REQUEST TASK STREAM",
            TaskType: "C2PA_SIGN WATERMARK",
            TaskStatus: "QUEUED RUNNING SUCCEEDED FAILED EXPIRED",
        }.items()
    },
}


@pytest.mark.parametrize(
    "enum_cls, expected", list(_WIRE_ENUMS.items()), ids=[cls.__name__ for cls in _WIRE_ENUMS]
)
def test_wire_enums(enum_cls, expected):
    assert issubclass(enum_cls, str)
    assert {m.name: m.value for m in enum_cls} == expected
    for name, value in expected.items():
        assert enum_cls[name] == value


def test_leaf_type_aliases():
    assert LeafType.C2PA_L1_TEST is LeafType.C2PA_L1_DUMMY
    assert LeafType.C2PA_L2_TEST is LeafType.C2PA_L2_DUMMY
    assert LeafType.CAWG_INTERIM_TEST is LeafType.CAWG_INTERIM_DUMMY


def test_signing_algorithm():
    # a plain enum: its values are tuples
    assert not issubclass(SigningAlgorithm, str)
    expected = {
        "ES256": ("ES256", "SHA256"),
        "ES384": ("ES384", "SHA384"),
        "ES512": ("ES512", "SHA512"),
        "EDDSA": ("EdDSA", None),
    }
    assert {m.name: m.value for m in SigningAlgorithm} == expected
    for name, (alg_name, hash_alg) in expected.items():
        assert (SigningAlgorithm[name].alg_name, SigningAlgorithm[name].hash_alg) == (
            alg_name,
            hash_alg,
        )


def test_algorithm_maps():
    curves = {alg: type(curve) for alg, curve in ALG_TO_CURVE.items()}
    assert curves == {
        SigningAlgorithm.ES256: ec.SECP256R1,
        SigningAlgorithm.ES384: ec.SECP384R1,
        SigningAlgorithm.ES512: ec.SECP521R1,
    }
    hash_types = {alg: type(hash_alg) for alg, hash_alg in ALG_TO_HASH.items()}
    assert hash_types == {
        SigningAlgorithm.ES256: hashes.SHA256,
        SigningAlgorithm.ES384: hashes.SHA384,
        SigningAlgorithm.ES512: hashes.SHA512,
        SigningAlgorithm.EDDSA: type(None),
    }


@pytest.mark.parametrize("profile", ["default", "fast", None, "skip4"])
def test_watermark_settings(profile):
    if profile in ("default", "fast"):
        assert WatermarkSettings(profile).profile is WatermarkProfile(profile)
    else:
        with pytest.raises(ValueError, match="Watermark profile must be 'default' or 'fast'."):
            WatermarkSettings(profile=profile)


def test_manifest_settings_validation():
    for kwargs, error, message in [
        ({"manifest_title": ""}, ValueError, "manifest_title must be a non-empty string"),
        ({"ingredient_title": 5}, ValueError, "ingredient_title must be a non-empty string"),
        ({"thumbnail_settings": {"size": "high"}}, TypeError, "thumbnail_settings must be"),
        ({"all_actions_included": "yes"}, TypeError, "all_actions_included must be bool"),
    ]:
        with pytest.raises(error, match=message):
            ManifestSettings(**kwargs)


def test_thumbnail_settings_validation():
    settings = ThumbnailSettings(policy="none", size="high")
    assert settings.policy is ThumbnailPolicy.NONE and settings.size is ThumbnailSize.HIGH
    for kwargs in ({"policy": "never"}, {"size": "large"}, {"size": None}):
        with pytest.raises(ValueError, match="Invalid C2PA thumbnail settings."):
            ThumbnailSettings(**kwargs)
