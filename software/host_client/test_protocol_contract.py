from rfcm_protocol import Packet, ReconnectClient, decode, encode
from mock_ps_server import OfflineMockTransport, handle

def main():
    p = Packet("status", b"")
    assert decode(encode(p)) == p
    assert decode(handle(encode(p))).command == "status.ok"
    assert b"TFDU_SHUTDOWN_PROGRAMMED" in decode(handle(encode(Packet("shutdown")))).payload
    try:
        decode(b"bad")
    except ValueError:
        pass
    else:
        raise AssertionError("bad magic not rejected")
    try:
        decode(b"RFCM")
    except ValueError:
        pass
    else:
        raise AssertionError("truncated header not rejected")

    error = decode(handle(encode(Packet("does_not_exist"))))
    assert error.command == "error"
    assert error.payload == b"unknown_command"

    connect_attempts = {"count": 0}

    def flaky_connector():
        connect_attempts["count"] += 1
        if connect_attempts["count"] == 1:
            raise OSError("offline connect refused")
        return OfflineMockTransport()

    client = ReconnectClient(flaky_connector, max_retries=2)
    assert client.request(Packet("status")).command == "status.ok"
    assert client.state == "CONNECTED"
    assert any(event.kind == "connect_error" for event in client.events)
    assert any(event.kind == "connected" for event in client.events)

    transports = [OfflineMockTransport(fail_first_exchange=True), OfflineMockTransport()]

    def reconnecting_connector():
        return transports.pop(0)

    client = ReconnectClient(reconnecting_connector, max_retries=2)
    assert client.request(Packet("status")).command == "status.ok"
    assert any(event.kind == "transport_error" for event in client.events)

    client = ReconnectClient(lambda: OfflineMockTransport(), max_retries=1)
    assert client.request(Packet("unknown")).command == "error"
    assert any(event.kind == "error_response" for event in client.events)
    print("HOST_CLIENT_PROTOCOL_TESTS=PASS")

if __name__ == "__main__":
    main()
