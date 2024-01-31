from argparse import ArgumentParser
import sys
from logging import getLogger, StreamHandler, Formatter, DEBUG
import serial
from updi import UpdiRev1, UpdiException, WIDTH_BYTE, WIDTH_3BYTE, WIDTH_WORD, KEY_OCD, KEY_NVMPROG

log = getLogger()
handler = StreamHandler(sys.stderr)
handler.setLevel(DEBUG)
handler.setFormatter(Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.setLevel(DEBUG)
log.addHandler(handler)


    
if __name__=="__main__":
    parser = ArgumentParser(description="AVR Basic SerialUPDI Remote Debugger")
    parser.add_argument("-p", "--part", help="MCU name (e.g. avr16ea48)", required=True)
    parser.add_argument("-P", "--port", help="Serial port used as SerialUPDI (e.g. COM5 or /dev/ttyS1)", required=True)
    parser.add_argument("-b", "--bps", help="Baud rate for communication (defaults to 115200)", type=int, default=115200)
    parser.add_argument("-r", "--rsp-port", help="TCP port number for RSP communcation with gdb", type=int, required=True)
    parser.add_argument("-F", "--enable-flashing", help="Enable features that require modifying NVM contents", action="store_true")
    args = parser.parse_args()
    # As serial port error can happen at any moment, it is never caught by Updi client
    uc = UpdiRev1(args.port, args.bps)
    try:
        # Identify the chip and determine UPDI, NVM & OCD versions
        updiver: int = uc.connect()
        sib: str = uc.read_sib().decode(errors="replace")
        signature = uc.load_burst(0x1100, burst=3)  # SIGROW.DEVICEID
        revid = uc.load_direct(0x0F01)              # SYSCFG.REVID
        
        sig = signature.hex("-").upper()
        rev = f"{chr((revid>>4)+65)}{revid&0x0F}" if revid & 0xF0 else chr(revid + 65)
        nvmver = sib[10]
        ocdver = sib[13]
        sibrev = sib[20:22]
        
        print(f"UPDI rev.{updiver}")
        print(f"SIB: {sib}")
        print(f"Signature: {sig} (revision {rev})")
        print(f"NVM: v{nvmver} / OCD: v{ocdver}")
        log.info(args)
        uc.disconnect()

    except serial.SerialException:
        print(f"Error while interacting serial port `{args.port}`", file=sys.stderr)
        exit(1)
    except UpdiException as ex:
        print(f"UPDI instruction `{ex.instruction}` failed", file=sys.stderr)
        uc.disconnect()
        exit(1)
    except KeyboardInterrupt:
        uc.disconnect()
        exit(0)