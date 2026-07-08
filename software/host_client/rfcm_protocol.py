from dataclasses import dataclass

MAGIC = b"RFCM"

@dataclass
class Packet:
    command: str
    payload: bytes = b""

@dataclass
class ClientEvent:
    kind: str
    detail: str

def encode(packet: Packet) -> bytes:
    cmd = packet.command.encode("ascii")
    if len(cmd) > 31:
        raise ValueError("command too long")
    return MAGIC + bytes([len(cmd)]) + cmd + len(packet.payload).to_bytes(2, "little") + packet.payload

def decode(data: bytes) -> Packet:
    if not data.startswith(MAGIC):
        raise ValueError("bad magic")
    if len(data) < 7:
        raise ValueError("truncated header")
    n = data[4]
    if len(data) < 5 + n + 2:
        raise ValueError("truncated command")
    command = data[5:5+n].decode("ascii")
    plen_at = 5 + n
    plen = int.from_bytes(data[plen_at:plen_at+2], "little")
    payload = data[plen_at+2:plen_at+2+plen]
    if len(payload) != plen:
        raise ValueError("truncated payload")
    return Packet(command, payload)

class ReconnectClient:
    def __init__(self, connector, max_retries=3):
        self.connector = connector
        self.max_retries = max_retries
        self.transport = None
        self.state = "DISCONNECTED"
        self.events = []

    def connect(self):
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                self.transport = self.connector()
                self.state = "CONNECTED"
                self.events.append(ClientEvent("connected", str(attempt)))
                return
            except OSError as exc:
                last_error = exc
                self.state = "DISCONNECTED"
                self.events.append(ClientEvent("connect_error", str(exc)))
        self.state = "FAILED"
        raise ConnectionError(f"connect failed: {last_error}")

    def request(self, packet: Packet) -> Packet:
        last_error = None
        for _ in range(self.max_retries + 1):
            if self.transport is None or self.state != "CONNECTED":
                self.connect()
            try:
                response = decode(self.transport.exchange(encode(packet)))
                if response.command == "error":
                    self.events.append(ClientEvent("error_response", response.payload.decode("ascii", errors="replace")))
                return response
            except OSError as exc:
                last_error = exc
                self.events.append(ClientEvent("transport_error", str(exc)))
                self.transport = None
                self.state = "DISCONNECTED"
        self.state = "FAILED"
        raise ConnectionError(f"request failed: {last_error}")
