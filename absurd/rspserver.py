import time
import sys
import socket
from typing import List, Literal, NoReturn
from logging import getLogger
log = getLogger(__name__)
from .debugger import OcdRev1

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
    def __init__(self, tcpport: int, debugger: OcdRev1) -> None:
        sv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sv.bind(("", tcpport))
        sv.listen()
        self.socket = sv
        self.dbg = debugger
        self.packparser = GdbPacketParser()
    
    def serve(self) -> None:
        self.dbg.attach()
        self.dbg.reset()
        client, addr = self.socket.accept()
        self.client = client
        log.info(f"Connected with {addr}")
        client.setblocking(True)
        try:
            while True:
                data = client.recv(1024)
                packets = self.packparser.process_bytes(data)

                if data:
                    log.debug(data)

                if b'\x03' in data:
                    client.sendall(b'+')
                    self.dbg.halt()
                    self.dbg.poll_halted()
                    self.send_packet("S02")

                for p in packets:
                    client.sendall(b'+')
                    self.handle_packet(p)
        finally:
            client.close()
    
    def handle_packet(self, packet:str):
        if packet.startswith("qSupported"):
            self.send_packet("PacketSize=1024")

        elif packet.startswith("qSymbol::"):
            self.send_packet("OK")
            
        elif packet.startswith("!"):
            self.send_packet("OK")

        elif packet.startswith("?"):
            # we're on a baremetal 8-bitter (an excuse for hardcoding SIGTRAP)
            self.send_packet("S05")

        elif packet.startswith("s"):
            # TODO: implement "step from..."
            # step should halt the CPU immediately
            self.dbg.step()
            self.send_packet("S05")

        elif packet.startswith("c"):
            # TODO: implement "continue from..."
            # We have to poll MCU for halted CPU, but we also have to accept interrupt request from GDB, so we poll both alternatingly
            self.dbg.run()
            while True:
                if self.dbg.is_halted():
                    self.send_packet("S05")
                    break
                b = self.client.recv(1)
                # We assume we don't receive any packet here
                if b'\x03' in b:
                    self.client.sendall(b'+')
                    self.dbg.halt()
                    self.dbg.poll_halted()
                    self.send_packet("S02")
                    break

        elif packet.startswith("g"):
            # General request for register file
            # 64 chars for GPRs, 2 for SREG, 4 for SP, 8 for byte PC (78 in total)
            gprs = self.dbg.get_register_file().hex()
            sreg = self.dbg.get_sreg()
            sp = self.dbg.get_sp()
            pc = self.dbg.get_pc() << 1
            sph = sp >> 8
            spl = sp & 0xFF
            pch = pc >> 8
            pcl = pc & 0xFF
            self.send_packet(f"{gprs}{sreg:02x}{spl:02x}{sph:02x}{pcl:02x}{pch:02x}0000")

        elif packet.startswith("m"):
            # Memory read access. Since modern AVRs map NVMs other than code flash to data space, we only support code (0x0-0x1FFFF) and data (0x800000-0x80FFFF)
            addr, length = parse_addr(packet[1:])
            if addr is None:
                self.send_packet("E00")
                return
            
            data = None
            if 0 <= addr < 0x200000:
                # Limit length to 128 B to be compatible with UPDI burst access
                data = self.dbg.read_flash(addr, length)
            elif 0x800000 <= addr < 0x810000:
                data = self.dbg.read_data(addr - 0x800000, length)
            
            if data:
                self.send_packet(data.hex())
            else:
                self.send_packet("E01")            

        elif packet.startswith("qRcmd"):
            # would be a good place to support strange things
            log.info(f"Monitor Command: {packet}")

        elif packet.startswith("k"):
            self.dbg.detach()
            raise StopIteration() # TODO: stop abuse

        else:
            self.send_packet("")
    

    def send_packet(self, data: str):
        checksum = f"{sum(data.encode('ascii')) % 256:02x}"
        escaped = data.replace("}", "}\x5d").replace("#","}\x03").replace("$","}\x04").replace("*","}\x0a")
        pack = f"${escaped}#{checksum}".encode("ascii")
        self.client.sendall(pack)

def parse_addr(s: str):
    try:
        addr, length = s.split(",")
        addr = int(addr, 16)
        length = int(length, 16)
        return addr, length
    except ValueError:
        return None, 0