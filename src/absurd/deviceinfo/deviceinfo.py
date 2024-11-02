from dataclasses import dataclass
import re
from typing import Tuple

# TODO: NVM controller, signature, bootrow, etc...

@dataclass
class DeviceInfo:
    flash_offset: int
    signature_addr: int
    signature: Tuple[int,int,int]
    flash_page_size: int
    eeprom_page_size: int

megaavr = re.compile(r"atmega(?P<flash>8|16|32|48)0(?P<pincount>8|9)$")
tinyavr = re.compile(r"attiny(?P<flash>2|4|8|16|32)(?P<series>0|1|2)(?P<pincount>2|4|6|7)$")
newavr = re.compile(r"avr(?P<flash>16|32|64|128)(?P<series>da|db|dd|du|ea|eb)(?P<pincount>14|20|28|32|48|64)$")

def get_deviceinfo(partname: str) -> DeviceInfo:
    partname = partname.lower()
    if m := megaavr.match(partname):
        highdensity = int(m.group("flash")) >= 32
        return DeviceInfo(
            flash_offset=0x4000,
            signature_addr=0x1100,
            signature=(0x1E, 0x00, 0x00),
            flash_page_size=128 if highdensity else 64,
            eeprom_page_size=64 if highdensity else 32
        )
    
    elif m := tinyavr.match(partname):
        highdensity = int(m.group("flash")) >= 32
        return DeviceInfo(
            flash_offset=0x8000,
            signature_addr=0x1100,
            signature=(0x1E, 0x00, 0x00),
            flash_page_size=128 if highdensity else 64,
            eeprom_page_size=64 if highdensity else 32
        )

    elif m := newavr.match(partname):
        family = m.group("series")
        if family in ("da", "db", "dd"):
            return DeviceInfo(
                flash_offset=0x800000,
                signature_addr=0x1100,
                signature=(0x1E, 0x00, 0x00),
                flash_page_size=512,
                eeprom_page_size=1
            )
        elif family in ("du"):
            return DeviceInfo(
                flash_offset=0x800000,
                signature_addr=0x1080,
                signature=(0x1E, 0x00, 0x00),
                flash_page_size=512,
                eeprom_page_size=1
            )
        elif family in ("ea"):
            return DeviceInfo(
                flash_offset=0x800000,
                signature_addr=0x1100,
                signature=(0x1E, 0x00, 0x00),
                flash_page_size=128 if m.group("flash") == "64" else 64,
                eeprom_page_size=8
            )
        elif family in ("eb"):
            return DeviceInfo(
                flash_offset=0x800000,
                signature_addr=0x1080,
                signature=(0x1E, 0x00, 0x00),
                flash_page_size=64,
                eeprom_page_size=8
            )
    raise ValueError

