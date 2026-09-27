"""Env-gated fixtures for live integration tests.

Every test in this package needs a live seventhings instance to talk to. They
are skipped (not failed) unless SEVENTHINGS_BASE_URL, SEVENTHINGS_USERNAME,
SEVENTHINGS_PASSWORD and SEVENTHINGS_CLIENT_ID are all set in the environment
(ping-only tests only need SEVENTHINGS_BASE_URL). Run them explicitly with::

    pytest -m integration
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator

import pytest

from seventhings import Client
from seventhings.models import TokenResponse

ENV_VARS = (
    "SEVENTHINGS_BASE_URL",
    "SEVENTHINGS_USERNAME",
    "SEVENTHINGS_PASSWORD",
    "SEVENTHINGS_CLIENT_ID",
)

_MISSING_ENV_MESSAGE = (
    "set SEVENTHINGS_BASE_URL, SEVENTHINGS_USERNAME, SEVENTHINGS_PASSWORD, "
    "SEVENTHINGS_CLIENT_ID to run integration tests"
)


def base_url() -> str:
    """The instance URL, or skip if not configured."""
    url = os.environ.get("SEVENTHINGS_BASE_URL")
    if not url:
        pytest.skip("set SEVENTHINGS_BASE_URL to run integration tests")
    return url


def credentials() -> tuple[str, str, str, str]:
    """(base_url, username, password, client_id), or skip if not fully configured."""
    values = [os.environ.get(name) for name in ENV_VARS]
    if not all(values):
        pytest.skip(_MISSING_ENV_MESSAGE)
    url, username, password, client_id = values
    assert url and username and password and client_id
    return url, username, password, client_id


def fresh_login() -> tuple[Client, TokenResponse]:
    """Perform a fresh login and return both the client and the token response.

    The caller is responsible for closing the returned client.
    """
    url, username, password, client_id = credentials()
    client = Client(url)
    token = client.auth.login(username, password, client_id)
    return client, token


def unique_suffix() -> str:
    """A millisecond timestamp, unique enough for names created by these tests."""
    return str(int(time.time() * 1000))


@pytest.fixture
def client() -> Iterator[Client]:
    """A logged-in sync client, closed after the test."""
    url, username, password, client_id = credentials()
    c = Client.with_credentials(url, username, password, client_id)
    try:
        yield c
    finally:
        c.close()
