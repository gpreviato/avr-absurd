from typing import Tuple

class DeviceInfo:
    flash_offset: int
    signature: Tuple[int,int,int]
    flash_page_size: int
    eeprom_page_size: int

    def __init__(self, signature: Tuple[int, int, int]) -> None:
        self.signature = signature


class AvrDB(DeviceInfo):
    flash_offset = 0x800000
    flash_page_size = 512
    eeprom_page_size = 32



DEVICES = {
    "avr128db48"
}