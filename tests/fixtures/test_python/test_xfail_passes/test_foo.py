from pytest import mark


@mark.xfail(reason="asdf")
def test_xfail_passes():
    pass
