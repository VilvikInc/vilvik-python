"""`vilvik login` - RFC 8628 device-authorization flow for the SDK.

The device endpoints are public, so this uses plain requests (no API key /
Transport). On success the minted key is cached via _credentials.
"""
from __future__ import annotations

import time
import webbrowser
from typing import Optional

import requests

from vilvik import _credentials
from vilvik._http import DEFAULT_BASE_URL, DEFAULT_USER_AGENT
from vilvik.exceptions import TimeoutError as VilvikTimeout, VilvikError


def login(
    *,
    base_url: str = DEFAULT_BASE_URL,
    open_browser: bool = True,
    poll_interval: Optional[float] = None,
    timeout: float = 900.0,
) -> str:
    """Run the device-authorization flow and cache the minted API key.

    Prints the verification URL + user code, opens a browser (unless
    open_browser=False), polls until the user approves, then saves and returns
    the key. Raises VilvikError on denial/expiry, VilvikTimeout on deadline.
    """
    base = base_url.rstrip("/")
    headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}

    start = requests.post(f"{base}/auth/device/code", json={}, headers=headers, timeout=30)
    start.raise_for_status()
    data = start.json()
    device_code = data["device_code"]
    interval = poll_interval if poll_interval is not None else float(data.get("interval", 5))
    complete = data.get("verification_uri_complete") or data.get("verification_uri", "")

    print("To authorize this device, open:\n    "
          f"{complete}\nand confirm the code: {data.get('user_code', '')}")
    if open_browser and complete:
        try:
            webbrowser.open(complete)
        except Exception:
            pass

    deadline = time.monotonic() + timeout
    while True:
        resp = requests.post(f"{base}/auth/device/token",
                             json={"device_code": device_code}, headers=headers, timeout=30)
        if resp.status_code == 200:
            key = resp.json()["api_key"]
            _credentials.save_api_key(key)
            print("Authorized. Credentials saved to " + _credentials.credentials_path())
            return key
        err = ""
        try:
            err = resp.json().get("error", "")
        except ValueError:
            pass
        if err == "authorization_pending":
            pass
        elif err == "slow_down":
            interval += 5
        elif err in ("access_denied", "expired_token"):
            raise VilvikError(f"Device authorization failed: {err}.")
        else:
            raise VilvikError(f"Unexpected device-token response ({resp.status_code}): {err or resp.text[:200]}")
        if time.monotonic() >= deadline:
            raise VilvikTimeout("Timed out waiting for device authorization.")
        time.sleep(interval)
