"""Tests for trufo.api.tps.enums."""

from trufo.api.tps.enums import DefaultCawgIdentityId


class TestDefaultCawgIdentityId:
    """DefaultCawgIdentityId is a str enum with the expected values."""

    def test_test_value(self):
        assert DefaultCawgIdentityId.TEST == "test"

    def test_org_interim_value(self):
        assert DefaultCawgIdentityId.ORG_INTERIM == "org_interim"

    def test_is_str_subclass(self):
        assert isinstance(DefaultCawgIdentityId.TEST, str)
        assert isinstance(DefaultCawgIdentityId.ORG_INTERIM, str)
