"""Shared pytest fixtures for the SDK test suite.

The tests intercept HTTP via the `responses` library so they never touch
a real Vilvik instance — fast, deterministic, and safe in CI.
"""

from __future__ import annotations

import pytest
import responses as responses_lib

from vilvik.client import Client

API_KEY = "vlk_test_abcdefghijklmnopqrstuvwxyz"
BASE_URL = "https://example.test/api/v1"


@pytest.fixture
def mock_api():
    """Yield a `responses.RequestsMock` mounted on a fixed base URL."""
    with responses_lib.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps


@pytest.fixture
def client():
    """A `Client` whose requests we can mock with `responses`."""
    return Client(api_key=API_KEY, base_url=BASE_URL, max_retries=0)
