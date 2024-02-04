from argparse import ArgumentParser
import sys
from logging import INFO, Filter, getLogger, StreamHandler, Formatter, DEBUG
import time
import re
import serial
from .debugger import OcdRev1
from .rspserver import RspServer
from .updi import UpdiRev1, UpdiRev3, UpdiException, WIDTH_BYTE, WIDTH_3BYTE, WIDTH_WORD, KEY_OCD, KEY_NVMPROG

log = getLogger()
handler = StreamHandler(sys.stderr)
handler.setLevel(DEBUG)
handler.setFormatter(Formatter("%(asctime)s [%(levelname)s] %(message)s"))
handler.addFilter(Filter("absurd.rspserver.rspserver"))
log.setLevel(DEBUG)
log.addHandler(handler)


def main():
    parser = ArgumentParser(description="AVR Basic SerialUPDI Remote Debugger")
    parser.add_argument("-p", "--part", help="MCU name (e.g. avr16ea48)", required=True)
    parser.add_argument("-P", "--port", help="Serial port used as SerialUPDI (e.g. COM5 or /dev/ttyS1)", required=True)
    parser.add_argument("-b", "--bps", help="Baud rate for communication (defaults to 115200)", type=int, default=115200)
    parser.add_argument("-r", "--rsp-port", help="TCP port number for RSP communcation with gdb", type=int, required=True)
    # parser.add_argument("-F", "--enable-flashing", help="Enable features that require modifying NVM contents", action="store_true")
    args = parser.parse_args()
    # As serial port error can happen at any moment, it is never caught by Updi client
    uc = UpdiRev1(args.port, args.bps)
    try:
        # Identify the chip and determine UPDI, NVM & OCD versions
        try:
            updiver: int = uc.connect()
        except UpdiException:
            uc.resynchronize()
            updiver: int = uc.connect()

        time.sleep(0.1)
        sib: str = uc.read_sib().decode(errors="replace")
        uc.key(KEY_NVMPROG)
        uc.store_csr(0x8, 0x59)
        uc.store_csr(0x8, 0x00)
        time.sleep(0.1)
        signature = uc.load_burst(0x1100, burst=3)  # SIGROW.DEVICEID
        revid = uc.load_direct(0x0F01)              # SYSCFG.REVID
        
        sig = signature.hex("-").upper()
        rev = f"{chr((revid>>4)+64)}{revid&0x0F}" if revid & 0xF0 else chr(revid + 64)
        nvmver = sib[10]
        ocdver = sib[13]
        sibrev = sib[20:22]

        print(f"UPDI rev.{updiver}")
        print(f"SIB: {sib}")
        print(f"Signature: {sig} (revision {rev})")
        print(f"NVM: v{nvmver} / OCD: v{ocdver}")
        
        uc.store_csr(0x8, 0x59)
        uc.store_csr(0x8, 0x00)
        time.sleep(0.1)
        uc.disconnect()

    except serial.SerialException:
        print(f"Error while interacting with serial port `{args.port}`", file=sys.stderr)
        exit(1)
    except UpdiException as ex:
        print(f"UPDI instruction `{ex.instruction}` failed", file=sys.stderr)
        uc.resynchronize()
        uc.disconnect()
        exit(1)
    
    # TODO: replace with a more decent mechanism for determining chip parameters
    megaavr = re.compile(r"atmega(?P<flash>8|16|32|48)0(?P<pincount>8|9)$")
    tinyavr = re.compile(r"attiny(?P<flash>2|4|8|16|32)(?P<series>0|1|2)(?P<pincount>2|4|6|7)$")
    newavr = re.compile(r"avr(?P<flash>16|32|64|128)(?P<series>da|db|dd|du|ea|eb)(?P<pincount>14|20|28|32|48|64)$")
    partname: str = args.part.lower()

    if megaavr.match(partname):
        # Mega 0
        flashoffset = 0x4000
    elif tinyavr.match(partname):
        # Tiny 0/1/2
        flashoffset = 0x8000
    elif newavr.match(partname):
        # Ex/Dx
        flashoffset = 0x800000
    else:
        print(f"Unknown/incompatible part `{partname}` specified")
        return
    
    # main loop
    updic = UpdiRev3(args.port, args.bps)
    try:
        # TODO: Check parts and set revision automatically
        dbg = OcdRev1(updic, flash_offset=flashoffset)
        sv = RspServer(args.rsp_port, dbg)
        sv.serve()
    
    except UpdiException as ex:
        print(f"UPDI instruction `{ex.instruction}` failed", file=sys.stderr)
        updic.disconnect()
        exit(1)
    except StopIteration:
        print(f"Normal termination", file=sys.stderr)
        updic.disconnect()
        exit(0)
    except KeyboardInterrupt:
        print(f"Terminated by Ctrl-C", file=sys.stderr)
        updic.disconnect()
        exit(0)

if __name__=="__main__":
    main()