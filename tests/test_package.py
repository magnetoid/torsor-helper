import torsor_mem


def test_version_exposed():
    assert isinstance(torsor_mem.__version__, str)
    assert torsor_mem.__version__.count(".") >= 1
