import pytest
import vilvik
from vilvik import _credentials

BASE = "https://example.test/api/v1"


def test_login_polls_then_saves_key(mock_api, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    mock_api.add("POST", f"{BASE}/auth/device/code", json={
        "device_code": "dc", "user_code": "WDJBMJHT",
        "verification_uri": "https://v/user/device/",
        "verification_uri_complete": "https://v/user/device/?code=WDJBMJHT",
        "expires_in": 900, "interval": 0}, status=200)
    mock_api.add("POST", f"{BASE}/auth/device/token", json={"error": "authorization_pending"}, status=400)
    mock_api.add("POST", f"{BASE}/auth/device/token",
                 json={"api_key": "vlk_live_minted", "scopes": ["imports:write"]}, status=200)

    key = vilvik.login(base_url=BASE, open_browser=False, poll_interval=0)
    assert key == "vlk_live_minted"
    assert _credentials.load_api_key() == "vlk_live_minted"


def test_login_raises_on_access_denied(mock_api, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    mock_api.add("POST", f"{BASE}/auth/device/code", json={
        "device_code": "dc", "user_code": "X", "verification_uri": "u",
        "verification_uri_complete": "u?code=X", "expires_in": 900, "interval": 0}, status=200)
    mock_api.add("POST", f"{BASE}/auth/device/token", json={"error": "access_denied"}, status=400)
    with pytest.raises(vilvik.VilvikError):
        vilvik.login(base_url=BASE, open_browser=False, poll_interval=0)
