import torsor_helper


def test_version_exposed():
    assert isinstance(torsor_helper.__version__, str)
    assert torsor_helper.__version__.count(".") >= 1
