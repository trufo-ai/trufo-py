"""Public local watermark settings validation."""

import pytest

from trufo.c2pa import WatermarkProfile, WatermarkSettings


@pytest.mark.parametrize("profile", ["default", "fast"])
def test_public_settings(profile):
    settings = WatermarkSettings(profile)
    assert settings.profile is WatermarkProfile(profile)


@pytest.mark.parametrize("profile", [None, "skip4"])
def test_invalid_profile(profile):
    with pytest.raises(ValueError, match="Watermark profile"):
        WatermarkSettings(profile=profile)
