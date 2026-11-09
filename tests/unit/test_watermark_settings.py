"""Public local watermark settings and lightweight SDK behavior."""

import os
import subprocess
import sys
from unittest.mock import patch

import pytest

from trufo import sign_c2pa_distributed, sign_c2pa_distributed_test, watermark_media
from trufo.c2pa import WatermarkProfile, WatermarkSettings


@pytest.mark.parametrize("profile", ["default", "fast"])
def test_public_settings(profile):
    settings = WatermarkSettings(profile)
    assert settings.profile is WatermarkProfile(profile)


@pytest.mark.parametrize("profile", [None, True, 1, {}, "FAST", "other", "skip4"])
def test_invalid_profile(profile):
    with pytest.raises(ValueError, match="Watermark profile"):
        WatermarkSettings(profile=profile)


def test_base_import_needs_no_optional_engines():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
class Block:
    def find_spec(self, fullname, *args):
        assert fullname.split('.')[0] not in {'torch', 'pawprint', 'tfprov'}, fullname
sys.meta_path.insert(0, Block())
from trufo.c2pa import WatermarkSettings
assert WatermarkSettings('fast').profile.value == 'fast'
""",
        ],
        env=os.environ.copy(),
        check=True,
    )


@pytest.mark.parametrize(
    "call", [watermark_media, sign_c2pa_distributed, sign_c2pa_distributed_test]
)
@pytest.mark.parametrize("settings", [{}, False, "fast"])
def test_wrong_type_precedes_optional_import(call, settings):
    with patch.dict(sys.modules, {"tfprov": None, "tfprov.util": None}):
        with pytest.raises(TypeError, match="WatermarkSettings"):
            call(b"media", {}, watermark_settings=settings)


@pytest.mark.parametrize(
    "settings",
    [
        None,
        WatermarkSettings(),
        WatermarkSettings("fast"),
    ],
)
def test_direct_watermark_boundary(settings):
    pawprint_import = pytest.importorskip("tfprov.util.pawprint_import")

    package = {"wid": "v1.000abc12345", "expires_at": "2099-01-01T00:00:00Z"}
    with patch.object(pawprint_import, "embed", return_value=b"marked") as embed:
        assert watermark_media(b"media", package, watermark_settings=settings) == b"marked"
    assert embed.call_args.args[0] == b"media"
    assert embed.call_args.args[1].wid == package["wid"]
    assert embed.call_args.kwargs == ({} if settings is None else {"mode": settings.profile.value})
