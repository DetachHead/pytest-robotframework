from pytest import mark


@mark.xfail(reason="asdf")
def test_xfail_fails():
    raise Exception
