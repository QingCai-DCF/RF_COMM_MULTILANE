from rfcm_protocol import Packet, decode, encode

def handle(frame: bytes) -> bytes:
    pkt = decode(frame)
    if pkt.command == "status":
        return encode(Packet("status.ok", b"offline"))
    if pkt.command == "shutdown":
        return encode(Packet("shutdown.ok", b"TFDU_SHUTDOWN_PROGRAMMED"))
    return encode(Packet("error", b"unknown_command"))

class OfflineMockTransport:
    def __init__(self, fail_first_exchange=False):
        self.fail_first_exchange = fail_first_exchange
        self.exchange_count = 0

    def exchange(self, frame: bytes) -> bytes:
        self.exchange_count += 1
        if self.fail_first_exchange and self.exchange_count == 1:
            raise OSError("offline link dropped")
        return handle(frame)
