from argparse import ArgumentParser
from updi import UpdiRev3, WIDTH_BYTE, WIDTH_3BYTE, WIDTH_WORD, KEY_OCD
import sys
from logging import getLogger, StreamHandler, Formatter, DEBUG

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

    updiclient = UpdiRev3(args.port, args.bps, args.enable_flashing)
    updiclient.connect()
    updiclient.load_direct(0x800012, data_width=WIDTH_BYTE)
    updiclient.store_direct(0x801234, 0x56, data_width=WIDTH_WORD)
    updiclient.resynchronize()
    updiclient.key(KEY_OCD)
    log.info(args)