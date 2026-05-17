"""Tests for trufo.api.tps.enums."""

from openprov.c2pa.helpers.cawg_identity import CawgIdentitySpecialId as EngineCawgIdentitySpecialId

from trufo.api.tps.enums import CawgIdentitySpecialId


class TestCawgIdentitySpecialId:
    """CawgIdentitySpecialId is a str enum with the expected values."""

    def test_test_value(self):
        assert CawgIdentitySpecialId.TEST == "test"

    def test_org_interim_value(self):
        assert CawgIdentitySpecialId.ORG_INTERIM == "org_interim"

    def test_is_str_subclass(self):
        assert isinstance(CawgIdentitySpecialId.TEST, str)
        assert isinstance(CawgIdentitySpecialId.ORG_INTERIM, str)

    def test_sdk_reexports_engine_enum(self):
        assert CawgIdentitySpecialId is EngineCawgIdentitySpecialId
