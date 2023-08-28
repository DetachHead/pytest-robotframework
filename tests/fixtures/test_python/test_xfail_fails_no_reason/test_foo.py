from pytest import mark


@mark.xfail
def test_xfail_fails():
    raise Exception
