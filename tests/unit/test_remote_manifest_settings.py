# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What RemoteManifestSettings accepts as a host that manifests may be fetched from."""

import pytest

from trufo.c2pa import DEFAULT_REMOTE_MANIFEST_HOSTS, RemoteManifestSettings


def test_defaults_fetch_from_the_default_hosts():
    settings = RemoteManifestSettings()
    assert settings.fetch is True
    assert settings.allowed_hosts == DEFAULT_REMOTE_MANIFEST_HOSTS == ("cai-manifests.adobe.com",)


def test_hosts_are_kept_as_a_lowercase_tuple():
    settings = RemoteManifestSettings(allowed_hosts=["Manifests.Example.com", "a.b-c.example"])
    assert settings.allowed_hosts == ("manifests.example.com", "a.b-c.example")


def test_no_hosts_is_allowed():
    assert RemoteManifestSettings(allowed_hosts=[]).allowed_hosts == ()


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
def test_refuses_anything_but_an_exact_host_name(host):
    with pytest.raises(ValueError, match="allowed_hosts"):
        RemoteManifestSettings(allowed_hosts=[host])


@pytest.mark.parametrize("hosts", ["example.com", [b"example.com"], None, [None]])
def test_refuses_hosts_that_are_not_a_list_of_strings(hosts):
    with pytest.raises(TypeError, match="allowed_hosts"):
        RemoteManifestSettings(allowed_hosts=hosts)


def test_refuses_a_fetch_that_is_not_a_bool():
    with pytest.raises(TypeError, match="fetch"):
        RemoteManifestSettings(fetch="no")
