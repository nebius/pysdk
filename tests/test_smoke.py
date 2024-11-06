from nebius import SDK


def test_sdk_init() -> None:
    sdk_instance = SDK()
    assert isinstance(sdk_instance, SDK)
