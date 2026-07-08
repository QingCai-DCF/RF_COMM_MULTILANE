from rfcm_protocol import Packet, decode, encode

def handle(frame: bytes) -> bytes:
    pkt = decode(frame)
    if pkt.command == "status":
        return encode(Packet("status.ok", b"offline"))
    if pkt.command == "shutdown":
        return encode(Packet("shutdown.ok", b"TFDU_SHUTDOWN_PROGRAMMED"))
    return encode(Packet("error", b"unknown_command"))
