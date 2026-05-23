from vilvik import _credentials


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _credentials.save_api_key("vlk_live_abc")
    assert _credentials.load_api_key() == "vlk_live_abc"


def test_load_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert _credentials.load_api_key() is None


def test_saved_file_is_user_only(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _credentials.save_api_key("vlk_live_abc")
    import os, stat
    mode = stat.S_IMODE(os.stat(_credentials.credentials_path()).st_mode)
    assert mode == 0o600
