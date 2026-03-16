from sm_bluesky.common.server import pulse_generator_shanghai_tech


def test_connect_hardware():
    server = pulse_generator_shanghai_tech.GeneratorServerShanghaiTech(
        host="localhost", port=8888
    )
    assert server.connect_hardware() is True
