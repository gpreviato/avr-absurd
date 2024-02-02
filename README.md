# AVR Basic SerialUPDI RSP Debugger
ABSURD is a Python-based GDB remote server that allows GDB to interact with the on-chip debugger (OCD) of modern AVR microcontrollers via SerialUPDI.  
ABSURD is licensed under the MIT License.

## Requirements
- SerialUPDI programmer (USB-UART adapter with its TX and RX connected by a fast diode)
- Modern AVR microcontroller with UPDI
  - MegaAVR 0-Series (ATmega__0_)
  - TinyAVR 0/1/2-Series (ATtiny__0_, ATtiny__1_, ATtiny__2_)
  - AVR Dx Series (AVR___DA__, AVR___DB__, AVR__DD__)
  - AVR Ex Series (AVR__EA__, AVR16EB__)
- PySerial Python library

## Usage
- Clone this repository
- Connect MCU and PC with a SerialUPDI programmer
- `python absurd -P [serial port] -p [MCU part name] -r [TCP port number]`
- Run `avr-gdb` and connect to the server by `target extended-remote :[TCP port number]`

## Features
- Two hardware breakpoints
- Single-stepping
- Halt on jump/call instructions
- Halt on interrupts
- Read/write access to register file, RAM, peripheral SFRs and NVMs

### Features to be supported
- NVM programming
- Software breakpoints

## For developers
Those who may want to experiment with UPDI or OCD can import the `absurd` package.
- `absurd.updi` contains `UpdiRevN` classes, which implement raw UPDI instructions
- `absurd.debugger.OcdRev1` wraps `UpdiRevN` and provides basic debugging functionalities. This may be helpful if you are coding your own debugger (to replace my terrible `RspServer`)
- My guesswork on OCD registers is available [here](./guesswork.md).