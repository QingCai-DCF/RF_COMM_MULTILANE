from dataclasses import dataclass

MAGIC = b"RFCM"

@dataclass
class Packet:
    command: str
    payload: bytes = b""

def encode(packet: Packet) -> bytes:
    cmd = packet.command.encode("ascii")
    if len(cmd) > 31:
        raise ValueError("command too long")
    return MAGIC + bytes([len(cmd)]) + cmd + len(packet.payload).to_bytes(2, "little") + packet.payload

def decode(data: bytes) -> Packet:
    if not data.startswith(MAGIC):
        raise ValueError("bad magic")
    n = data[4]
    command = data[5:5+n].decode("ascii")
    plen_at = 5 + n
    plen = int.from_bytes(data[plen_at:plen_at+2], "little")
    payload = data[plen_at+2:plen_at+2+plen]
    if len(payload) != plen:
        raise ValueError("truncated payload")
    return Packet(command, payload)
