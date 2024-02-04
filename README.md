# AVR Basic SerialUPDI RSP Debugger
ABSURD is a Python-based GDB remote server that allows GDB to interact with the on-chip debugger (OCD) of modern AVR microcontrollers via SerialUPDI.  
ABSURD is licensed under the MIT License.

This project is currently at the proof-of-concept level. While it has been confirmed that basic GDB operations such as `si` and `hbreak` work on AVR128DB48 and AVR32EA48, many features are yet to be implemented, and some may not work properly even if implemented.

## Requirements
- SerialUPDI programmer (USB-UART adapter with its TX and RX connected by a fast diode)
- Modern AVR microcontroller with UPDI
  - MegaAVR 0-Series (`ATmega__0_`)
  - TinyAVR 0/1/2-Series (`ATtiny__0_`, `ATtiny__1_`, `ATtiny__2_`)
  - AVR Dx Series (`AVR___DA__`, `AVR___DB__`, `AVR__DD__`)
  - AVR Ex Series (`AVR__EA__`, `AVR16EB__`)
- pySerial Python library

## Usage
- Clone this repository
- Install ABSURD with `pip install -e .`
- Connect MCU to PC with a SerialUPDI programmer
- `avr-absurd -P [serial port] -p [MCU part name] -r [TCP port number]`
  - or `python -m absurd` instead of `avr-absurd` if you didn't install ABSURD
- Run `avr-gdb` and connect to the server with `target extended-remote :[TCP port number]`

## Features
- Two hardware breakpoints
- Single-stepping
- Halt on jump/call instructions
- Halt on interrupts
- Read/write access to register file, RAM and peripheral SFRs
- Read access to flash

### TODO
- NVM programming
- Software breakpoints
- Replace RspServer with something more decent

## For developers
Those who may want to experiment with UPDI or OCD can import the `absurd` package.
- `absurd.updi` contains `UpdiRevN` classes, which implement raw UPDI instructions
- `absurd.debugger.OcdRev1` wraps `UpdiRevN` and provides basic debugging functionalities. This may be helpful if you are coding your own debugger (to replace my terrible `RspServer`)
- My guesswork on OCD registers is available [here](./guesswork.md).