# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared test fixtures for trufo-py tests."""

import io
import ipaddress
import json
import logging
import socket
from types import SimpleNamespace

import pytest
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_private_key,
)
from requests.adapters import HTTPAdapter
from urllib3.connectionpool import HTTPConnectionPool

from trufo.crypt.kms import AWSKMSPrivateKey, GCPKMSPrivateKey

# signing hash by key size, as the KMS key spec fixes it
_HASHES = {256: hashes.SHA256(), 384: hashes.SHA384()}


class _FakeAWSKMSClient:
    """boto3 KMS client stand-in that signs with a local EC key."""

    def __init__(self, private_pem: bytes):
        self._key = load_pem_private_key(private_pem, password=None)

    def get_public_key(self, KeyId):
        der = self._key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        return {"PublicKey": der}

    def sign(self, KeyId, Message, MessageType, SigningAlgorithm):
        assert (MessageType, SigningAlgorithm) == ("RAW", f"ECDSA_SHA_{self._key.key_size}")
        return {"Signature": self._key.sign(Message, ec.ECDSA(_HASHES[self._key.key_size]))}


class _FakeGCPKMSClient:
    """Cloud KMS client stand-in that signs with a local EC key."""

    def __init__(self, private_pem: bytes):
        self._key = load_pem_private_key(private_pem, password=None)

    def get_public_key(self, request):
        pem = self._key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        return SimpleNamespace(pem=pem.decode())

    def asymmetric_sign(self, request):
        ((digest_name, digest),) = request["digest"].items()
        assert digest_name == f"sha{self._key.key_size}"
        prehashed = ec.ECDSA(Prehashed(_HASHES[self._key.key_size]))
        return SimpleNamespace(signature=self._key.sign(digest, prehashed))


class TrufoAPI:
    """Trufo's API, and every other HTTP host, as a test scripts it for requests sent with
    ``requests``, in place of its transport adapter; a request that gets past it to ``urllib3``
    fails the test.

    ``answer(method, url, *responses)`` scripts what requests to ``url`` (with its query) get;
    several responses are given in order, the last repeating. A response is a JSON body or
    bytes, sent with status 200, a ``(status, body)`` pair, an exception to raise, or a function
    of the request that returns one of these. ``requests`` records each request as its session
    prepared it, with any auth, cookies and session defaults: ``method``, ``url``, ``headers``,
    ``body``, ``timeout``, and ``json``, the body decoded when it is JSON and not empty. A request
    nobody scripted fails the test.
    """

    def __init__(self):
        self.requests = []
        self._answers = {}

    def answer(self, method, url, *responses):
        self._answers[(method, url)] = list(responses)

    def send(self, prepared, timeout=None, **kwargs):
        is_json = prepared.body and prepared.headers.get("Content-Type") == "application/json"
        request = SimpleNamespace(
            method=prepared.method,
            url=prepared.url,
            headers=prepared.headers.copy(),
            body=prepared.body,
            json=json.loads(prepared.body) if is_json else None,
            timeout=timeout,
        )
        self.requests.append(request)
        queue = self._answers.get((request.method, request.url))
        if not queue:
            pytest.fail(f"Unscripted request: {request.method} {request.url}", pytrace=False)
        answer = queue.pop(0) if len(queue) > 1 else queue[0]
        if callable(answer):
            answer = answer(request)
        if isinstance(answer, BaseException):
            raise answer
        status, body = answer if isinstance(answer, tuple) else (200, answer)
        response = requests.Response()
        response.status_code, response.url, response.encoding = status, request.url, "utf-8"
        response.request = prepared
        response.raw = io.BytesIO(body if isinstance(body, bytes) else json.dumps(body).encode())
        return response


@pytest.fixture(autouse=True)
def trufo_api(monkeypatch):
    """Every request a test sends with ``requests``, scripted and recorded (see ``TrufoAPI``)."""
    api = TrufoAPI()
    # a bound method stays bound to api when read from an adapter
    monkeypatch.setattr(HTTPAdapter, "send", api.send)
    # what an adapter sender bound before the test would reach
    monkeypatch.setattr(HTTPConnectionPool, "urlopen", _unscripted)
    return api


def _unscripted(*args, **kwargs):
    pytest.fail("A request was sent past the scripted API.", pytrace=False)


@pytest.fixture(autouse=True)
def loopback_only(monkeypatch):
    """Fails the test when anything, by any client, tries to look up a host name other than
    ``localhost`` or to connect a socket off this machine."""
    attempts = []

    def guard(connect):
        def checked(sock, address):
            if not _on_this_machine(sock, address):
                attempts.append(address)
                pytest.fail(f"A connection to {address} was attempted.", pytrace=False)
            return connect(sock, address)

        return checked

    def guard_lookup(lookup):
        def checked(host, *args, **kwargs):
            if not _needs_no_lookup(host):
                attempts.append(host)
                pytest.fail(f"A lookup of {host!r} was attempted.", pytrace=False)
            return lookup(host, *args, **kwargs)

        return checked

    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, guard(getattr(socket.socket, name)))
    for name in ("getaddrinfo", "gethostbyname"):
        monkeypatch.setattr(socket, name, guard_lookup(getattr(socket, name)))
    yield
    # also when the attempt was in a thread, whose failure does not reach the test
    assert attempts == [], f"Lookups or connections were attempted off this machine: {attempts}."


def _needs_no_lookup(host):
    """Whether ``host`` is none, ``localhost`` or an IP address, which resolve without a lookup."""
    try:
        return host in (None, "") or host.lower() == "localhost" or bool(ipaddress.ip_address(host))
    except ValueError:
        return False


def _on_this_machine(sock, address):
    """Whether ``address`` is a Unix socket or a loopback IP address."""
    if sock.family == socket.AF_UNIX:
        return True
    try:
        return ipaddress.ip_address(address[0]).is_loopback
    except ValueError:
        # a host name, which connecting would look up
        return False


@pytest.fixture
def logged(caplog):
    """Logging captured from DEBUG up, and a function that returns all the captured records hold:
    their formatted text and each record's attributes (its message, args and any extra fields)."""
    caplog.set_level(logging.DEBUG)
    return lambda: caplog.text + "".join(repr(vars(record)) for record in caplog.records)


@pytest.fixture
def kms_keys():
    """Factories wrapping a local EC private key PEM in each KMS key class, on a fake client."""
    return {
        "aws-kms": lambda pem: AWSKMSPrivateKey(_FakeAWSKMSClient(pem), "key-id"),
        "gcp-kms": lambda pem: GCPKMSPrivateKey(_FakeGCPKMSClient(pem), "key-version-name"),
    }
