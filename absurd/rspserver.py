import time
import sys
import socket
from typing import List, Literal, NoReturn
from logging import getLogger
log = getLogger(__name__)


def verify_checksum(payload:bytes, checksum:bytes) -> bool:
    try:
        calcdcs = sum(payload) % 256
        recvdcs = int(checksum[:2].decode(encoding="ascii", errors="ignore"), 16)
        return calcdcs == recvdcs
    except ValueError:
        return False

def unescape(data:bytes) -> str:
    parts = data.split(b'}')
    ret = [parts[0].decode("ascii")]
    for run in parts[1:]:
        if len(run) > 0:
            ret.append(chr(run[0] ^ 0x20))
        ret.append(run[1:].decode("ascii"))
    return "".join(ret)

class GdbPacketParser:
    def __init__(self) -> None:
        self.expecting: Literal["$", "#", "CS1", "CS2"] = "#"
        self.pendingpacket: bytes = bytes()
    
    def process_bytes(self, data:bytes) -> List[str]:
        if not data:
            return []
        candidates = data.split(b'$')
        candidates[0] = self.pendingpacket + candidates[0]
        # check if the last is compelete separately
        completepackets = [cand.split(b'#', 1) for cand in candidates[:-1] if b'#' in cand[:-2]]
        if b'#' in candidates[-1][:-2]:
            completepackets.append(candidates[-1].split(b'#', 1))
            self.pendingpacket = bytes()
        else:
            self.pendingpacket = candidates[-1]
        # ASCII-safety
        checkedpackets = [(payload, checksum) for (payload, checksum) in completepackets if all(x < 0x80 for x in payload)]
        # Unescape and verify checksum
        unescapedpackets = [up for (payload, checksum) in checkedpackets if verify_checksum((up := unescape(payload)).encode("ascii"), checksum)]
        return unescapedpackets


class RspServer:
    def __init__(self, tcpport: int, debugger) -> None:
        sv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sv.bind(("", tcpport))
        sv.listen()
        self.socket = sv
        self.debugger = debugger
        self.packparser = GdbPacketParser()
    
    def serve(self) -> None:
        client, addr = self.socket.accept()
        self.client = client
        log.info(f"Connected with {addr}")
        client.setblocking(True)
        try:
            while True:
                data = client.recv(1024)
                packets = self.packparser.process_bytes(data)
                if data:
                    print(data)
                if b'\x03' in data:
                    client.sendall(b'+')
                    self.send_packet("S05")
                if not packets:
                    pass
                    # client.sendall(b'-')
                for p in packets:
                    client.sendall(b'+')
                    self.handle_packet(p)
        finally:
            client.close()
    
    def handle_packet(self, packet:str):
        if packet.startswith("qSupported"):
            self.send_packet("PacketSize=10000")
        elif packet.startswith("qSymbol::"):
            self.send_packet("OK")
        elif packet.startswith("?"):
            self.send_packet("S05")
        elif packet.startswith("s"):
            self.send_packet("S05")
        elif packet.startswith("g"):
            self.send_packet("123456789abcdef123456789abcdef123412345678123456789abcdef123456789abcdef123412")
        else:
            self.send_packet("")
    

    def send_packet(self, data: str):
        checksum = f"{sum(data.encode('ascii')) % 256:02x}"
        escaped = data.replace("}", "}\x5d").replace("#","}\x03").replace("$","}\x04").replace("*","}\x0a")
        pack = f"${escaped}#{checksum}".encode("ascii")
        self.client.sendall(pack)

