import time
from typing import Tuple, Literal
from logging import getLogger
log = getLogger(__name__)
import serial

class UpdiException(Exception):
    def __init__(self, instruction:str, *args: object) -> None:
        super().__init__(*args)
        self.instruction = instruction

class UpdiRev3:
    """
    UPDI client as specified in AVR EA's datasheet (revision 3)
    """

    def __init__(self, serialport:str, baudrate:int):
        self.uart = serial.Serial(baudrate=baudrate, parity=serial.PARITY_EVEN, stopbits=serial.STOPBITS_TWO, timeout=1.0)
        self.uart.port = serialport
        self.uart.dtr = False
    
    def connect(self) -> int:
        """
        Assumes control of the serial port and connects to the UPDI on-chip interface.
        DTR will be deasserted and then reasserted to generate an HV pulse on SerialUPDI adapters supporting HV-UPDI.
        """
        # there's no spec for how long HV has to be kept asserted, but 1 ms sounds long enough
        log.debug("Opening serial port")
        self.uart.dtr = False
        try:
            self.uart.open()
        except serial.SerialException:
            log.error(f"Could not open {self.uart.name}")
            raise
        
        log.debug("Emitting HV pulse and handshake")
        time.sleep(0.001)
        self.uart.dtr = True
        time.sleep(0.001)
        self.uart.dtr = False
        # Handshake. Spec says t(Deb0) within 200 ns and 1 us, which is hard to comply; usually much longer pulse works
        self.uart.send_break(0.000_001)
        # We have 13 ms before sending Sync char
        time.sleep(0.005)
        # Clear read buffer as it may contain Break ('\0' w/ FE) or other garbage
        self.uart.reset_input_buffer()
        
        # Added for compatibility with T412
        # stcs CTRLB, 0x08 (Disable contention check)
        self.uart.write(b"U\xc3\x08")
        self.uart.flush()
        self.uart.read(3)
        self.uart.reset_input_buffer()

        # Issue a harmless command ("ldcs CTRLA") to consume the Sync char
        self.uart.write(b'U\x80')
        self.uart.flush()
        buffer = self.uart.read(3)
        if len(buffer) != 3:
            # timed out, connection failed
            log.error(f"Initial command timed out; could not connect to MCU (expected 3 bytes, got '{buffer.hex(' ')}')")
            raise UpdiException("ldcs", "`ldcs CTRLA` after handshake failed")
        
        log.info(f"UPDI version: {buffer[2] >> 4}")
        return buffer[2] >> 4
    
    def disconnect(self):
        """
        issues `stcs CTRLB, UPDIDIS` and closes serial port if it is open
        """
        if self.uart.is_open:
            self.store_csr(0x3, 4)
            self.uart.close()

    def resynchronize(self) -> int:
        """
        Resynchronizes UPDI communication by sending Break and clearing any communication error
        returns: error code as given in STATUSB.PESIG
        """
        # 25 ms is long enough to be recognized as Break by slowest specified baud rate 
        log.debug("Transmitting 25 ms break")
        self.uart.send_break(0.025)
        # ldcs STATUSB
        log.debug("Clearing PESIG by read access")
        self.uart.reset_input_buffer()
        self.uart.write(b'U\x81')
        self.uart.flush()
        buffer = self.uart.read(3)
        if len(buffer) != 3:
            log.error(f"'ldcs STATUSB' after Break timed out; could not connect to MCU (expected 3 bytes, got '{buffer.hex(' ')}')")
            raise UpdiException("ldcs", "`ldcs STATUSB` following a BREAK character failed")
            
        log.info(f"UPDI resynchronized; error code: {buffer[2]:02x}")
        return buffer[2]
    
    def command(self, txdata: bytes, n_expected=0, skip_sync=False) -> Tuple[bool, bytes]:
        """
        Transmit `txdata` and wait for reception of `n_expected` bytes.
        Sync character ('U') is automatically prepended to `txdata` unless `skip_sync` is set
        """
        n_tx = len(txdata) if skip_sync else len(txdata) + 1
        self.uart.reset_input_buffer()
        log.info(f"Command: {txdata.hex(' ')} -> {n_expected} B")
        if skip_sync:
            self.uart.write(txdata)
        else:
            self.uart.write(b'U' + txdata)
        self.uart.flush()
        
        echo = self.uart.read(n_tx)
        # log.debug(f"command echo: {echo}")
        if len(echo) != n_tx:
            log.error(f"Instruction echo not received (expected {n_tx} byte(s), got '{echo.hex(' ')}')")
            return False, b"E"
        
        if n_expected == 0:
            return True, bytes()
        
        buffer = self.uart.read(n_expected)
        # log.debug(f"command return: {buffer}")
        if len(buffer) != n_expected:
            log.error(f"Expected response not received (expected {n_expected} byte(s), got '{buffer.hex(' ')}')")
            return False, b"R"
        log.info(f"Response: {buffer.hex(' ')}")
        return True, buffer
    

    def load_csr(self, addr: int) -> int:
        """
        `ldcs addr` instruction (opcode 0x8_)
        """
        assert 0 <= addr <= 0xF
        succ, val = self.command(bytes((0x80 | addr, )), n_expected=1)
        if not succ:
            raise UpdiException("ldcs")
        return val[0]
    
    
    def store_csr(self, addr: int, value: int):
        """
        `stcs addr, value` instruction (opcode 0xC_)
        """
        assert 0 <= addr <= 0xF
        assert 0 <= value <= 0xFF
        succ, val = self.command(bytes((0xC0 | addr, value)))
        if not succ:
            raise UpdiException("stcs")
        
    
    def read_sib(self, size: Literal[0b00, 0b01, 0b10] = 2) -> bytes:
        """
        `key.sib width` instruction (opcode 0xE_)  
        width: 0=8 B; 1=16 B; 2=32 B  
        * width=2 is undocumented, but is used by official debuggers, and in fact 32 B is sent even if width=1
        """
        assert 0 <= size <= 3
        succ, val = self.command(bytes((0xE4 | size,)), n_expected=32)
        if not succ:
            raise UpdiException("sib")
        return val 
    
    
    def key(self, key: bytes):
        """
        `key` instruction (opcode 0xE_)  
        The keys are ASCII strings available as consts.
        """
        assert len(key) == 8
        succ, val = self.command(bytes((0xE0,)) + key[::-1])
        if not succ:
            raise UpdiException("key")
        
    
    def repeat(self, count: int):
        """
        `repeat count` instruction. (opcode 0xA0)
        * count can be byte or word, but it is limited to 255, so the word-width variant is not so meaningful
        """
        assert 1<=count<=0x100
        succ, val = self.command(bytes((0xA0, count-1)))
        if not succ:
            raise UpdiException("repeat")
        
    
    def load_direct(self, addr: int, addr_width: Literal[0, 1, 2] = 2, data_width: Literal[0, 1] = 0) -> int:
        """
        `lds addr` instruction. (opcode 0x0_)
        addr_width: address width (0=B; 1=W; 2=3B)  
        data_width: data width (0=B; 1=W)  
        * prefixing with `repeat` is supported by hardware, but omitted from this library
        """
        assert (addr_width==0 and 0<=addr<=0xFF) or (addr_width==1 and 0<=addr<=0xFFFF) or (addr_width==2 and 0<=addr<=0xFFFFFF)
        assert 0 <= data_width <= 1
        if addr_width==0:
            succ, val = self.command(bytes((0x00 | data_width, addr)), n_expected=data_width + 1)
        elif addr_width==1:
            succ, val = self.command(bytes((0x04 | data_width, addr & 0xFF, addr >> 8)), n_expected=data_width + 1)
        else:
            succ, val = self.command(bytes((0x08 | data_width, addr & 0xFF, (addr >> 8) & 0xFF, addr >> 16)), n_expected=data_width + 1)

        if succ and data_width==0:
            return val[0] 
        elif succ:
            return (val[1] << 8) | val[0]  
        else:
            log.error("lds instruction failed")
            raise UpdiException("lds")
        
    
    def store_direct(self, addr:int, data:int, addr_width:Literal[0,1,2]=2, data_width:Literal[0,1]=0) -> None:
        """
        `sts addr, val` instruction. (opcode 0x4_)
        addr_width: address width (0=B; 1=W; 2=3B)  
        data_width: data width (0=B; 1=W)  
        * prefixing with `repeat` is supported by hardware, but omitted from this library
        """
        assert (addr_width==0 and 0<=addr<=0xFF) or (addr_width==1 and 0<=addr<=0xFFFF) or (addr_width==2 and 0<=addr<=0xFFFFFF)
        assert (data_width==0 and 0<=data<=0xFF) or (data_width==1 and 0<=data<=0xFFFF)

        if addr_width==0:
            succ, val = self.command(bytes((0x40 | data_width, addr)), n_expected=1)
        elif addr_width==1:
            succ, val = self.command(bytes((0x44 | data_width, addr & 0xFF, addr >> 8)), n_expected=1)
        else:
            succ, val = self.command(bytes((0x48 | data_width, addr & 0xFF, (addr >> 8) & 0xFF, addr >> 16)), n_expected=1)
        if not succ or val[0]!=0x40:
            log.error(f"sts instruction failed at addressing stage: {val}")
            raise UpdiException("sts", "`sts` instruction did not receive ACK in address stage")

        databytes = bytes((data,)) if data_width==0 else bytes((data & 0xFF, data >> 8))
        succ, val = self.command(databytes, n_expected=1, skip_sync=True)
        if not succ or val[0]!=0x40:
            log.error(f"sts instruction failed at data stage: {val}")
            raise UpdiException("sts", "`sts` instruction did not receive ACK in data stage")


    def load_pointer(self, addr_width:Literal[0,1,2]=2) -> int:
        """
        `ld ptr` instruction (opcode 0x2_)
        reads the pointer for indirect access by `ld`/`st` instructions.
        addr_width: address width (0=B; 1=W; 2=3B)
        """
        succ, val = self.command(bytes((0x28 | addr_width,)), n_expected=1 + addr_width)
        if not succ:
            raise UpdiException("ld", "`ld ptr`")
        
        if addr_width == 0:
            return val[0]
        elif addr_width == 1:
            return val[0] | (val[1] << 8)
        else:
            return val[0] | (val[1] << 8) | (val[2] << 16)
        
        
    def store_pointer(self, addr:int, addr_width:Literal[0,1,2]=2) -> None:
        """
        `st ptr` instruction (opcode 0x6_)
        sets the pointer for indirect access by `ld`/`st` instructions.
        addr_width: address width (0=B; 1=W; 2=3B)
        """
        assert (addr_width==0 and 0<=addr<=0xFF) or (addr_width==1 and 0<=addr<=0xFFFF) or (addr_width==2 and 0<=addr<=0xFFFFFF)

        if addr_width==0:
            succ, val = self.command(bytes((0x68, addr)), n_expected=1)
        elif addr_width==1:
            succ, val = self.command(bytes((0x69, addr & 0xFF, addr >> 8)), n_expected=1)
        else:
            succ, val = self.command(bytes((0x6A, addr & 0xFF, (addr >> 8) & 0xFF, addr >> 16)), n_expected=1)
        if not succ or val[0]!=0x40:
            log.error(f"st ptr instruction failed: {val}")
            raise UpdiException("st", "`st ptr`")
        
    
    def load_indirect(self, data_width:Literal[0,1]=0, addr_step:Literal[0,1,3]=1, burst=1) -> bytes:
        """
        `ld *ptr` instruction (opcode 0x2_)
        loads data at the address pointed by the pointer.
        data_width: (0=B; 1=W)
        addr_step: (0=No change, 1=post-increment, 3=post-decrement)
        burst: number of bytes/words stored in burst (must match the operand of preceding `repeat` instruction)
        return: bytes for both `data_width`s (low byte first to match memory layout)
        """
        succ, val = self.command(bytes((0x20 | (addr_step << 2) | data_width,)), n_expected=burst * (data_width + 1))
        if not succ:
            raise UpdiException("ld", f"`ld` expected {burst} {['byte','word'][data_width]}(s)")
        return val 

    def store_indirect(self, data: bytes, data_width:Literal[0,1]=0, addr_step:Literal[0,1,3]=1, burst=1) -> None:
        """
        `st *ptr` instruction (opcode 0x6_)
        stores `data` at the address pointed by the pointer.
        data_width: (0=B; 1=W)
        addr_step: (0=No change, 1=post-increment, 3=post-decrement)
        burst: number of bytes/words stored in burst (must match the operand of preceding `repeat` instruction)
        """
        assert len(data) >= (burst if data_width == 0 else 2 * burst)
        assert 1 <= burst <= 0xFF
        succ, val = self.command(bytes((0x60 | (addr_step << 2) | data_width,)))
        if not succ:
            log.error(f"st *ptr instruction failed in instruction stage: {val}")
            raise UpdiException("st", f"`st` did not receive own echo in instruction stage")

        for i in range(burst):
            if data_width == 0:
                succ, val = self.command(bytes((data[i],)), n_expected=1, skip_sync=True)
            else:
                succ, val = self.command(bytes((data[2 * i], data[2 * i + 1])), n_expected=1, skip_sync=True)

            if not succ or val[0]!=0x40:
                log.error(f"st *ptr instruction failed in data stage: {val}")
                raise UpdiException("st", f"`st` did not receive enough bytes in data stage")

    def load_burst(self, addr: int, data_width: Literal[0, 1] = 0, burst=1) -> bytes:
        """
        burst indirect load using successive `st ptr`, `repeat` and `ld *ptr++` instructions.
        """
        self.store_pointer(addr)
        self.repeat(burst)
        return self.load_indirect(data_width=data_width, addr_step=1, burst=burst)
    
    def store_burst(self, addr: int, data: bytes, data_width: Literal[0, 1] = 0, burst=1) -> None:
        """
        burst indirect store using successive `st ptr`, `repeat` and `st *ptr++` instructions.
        """
        self.store_pointer(addr)
        self.repeat(burst)
        self.store_indirect(data, data_width=data_width, addr_step=1, burst=burst)
