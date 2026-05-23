import vilvik


def test_public_exports_present():
    for name in ("push", "CaptureReport", "CaptureError", "ImportRecord", "Client"):
        assert hasattr(vilvik, name), name
        assert name in vilvik.__all__, name


def test_version_consistent():
    from vilvik._http import DEFAULT_USER_AGENT
    assert vilvik.__version__ in DEFAULT_USER_AGENT
