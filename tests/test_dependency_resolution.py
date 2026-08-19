def test_python_dateutil_resolves_as_installed_package():
    import dateutil
    import dateutil.tz

    assert dateutil.__path__
    assert callable(dateutil.tz.gettz)
