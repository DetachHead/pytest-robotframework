from pytest import CaptureFixture


def test_fixture(capfd: CaptureFixture[str]):
    assert isinstance(capfd, CaptureFixture)
