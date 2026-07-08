from rfcm_protocol import Packet, decode, encode
from mock_ps_server import handle

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
    print("HOST_CLIENT_PROTOCOL_TESTS=PASS")

if __name__ == "__main__":
    main()
