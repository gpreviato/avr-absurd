from typing import Literal, Optional,Tuple
from updirev3 import UpdiRev3

class UpdiRev2(UpdiRev3):
    def load_indirect(self, data_width:Literal[0,1]=0, addr_step:Literal[0,1]=0, burst=1) -> Tuple[bool, bytes | Literal['EchoTimedOut', 'ResponseTimedOut']]:
        """
        `ld *ptr` instruction (opcode 0x2_)
        loads data at the address pointed by the pointer.
        data_width: (0=B; 1=W)
        addr_step: (0=No change, 1=post-increment)
        burst: number of bytes/words stored in burst (must match the operand of preceding `repeat` instruction)
        return: bytes for both `data_width`s (low byte first to match memory layout)
        """
        return super().load_indirect(data_width, addr_step, burst)

    def store_indirect(self, data: bytes, data_width:Literal[0,1]=0, addr_step:Literal[0,1]=0, burst=1) -> Tuple[bool, Optional[Literal["InstructionNotEchoed", "DataNacked"]]]:
        """
        `st *ptr` instruction (opcode 0x6_)
        stores `data` at the address pointed by the pointer.
        data_width: (0=B; 1=W)
        addr_step: (0=No change, 1=post-increment)
        burst: number of bytes/words stored in burst (must match the operand of preceding `repeat` instruction)
        """
        return super().store_indirect(data, data_width, addr_step, burst)

class UpdiRev1(UpdiRev2):
    def load_pointer(self, addr_width:Literal[0,1]=1) ->Tuple[bool, int | Literal['EchoTimedOut', 'ResponseTimedOut']]:
        """
        `ld ptr` instruction (opcode 0x2_)
        reads the pointer for indirect access by `ld`/`st` instructions.
        addr_width: address width (0=B; 1=W)
        """
        return super().load_pointer(addr_width)

        
    def store_pointer(self, addr, addr_width:Literal[0,1]=1) ->Tuple[bool, Optional[Literal['EchoTimedOut', 'ResponseTimedOut']]]:
        """
        `st ptr` instruction (opcode 0x6_)
        sets the pointer for indirect access by `ld`/`st` instructions.
        addr_width: address width (0=B; 1=W; 2=3B)
        """
        return super().store_pointer(addr, addr_width)
    
    def load_direct(self, addr: int, addr_width: Literal[0, 1] = 1, data_width: Literal[0, 1] = 0) -> Tuple[bool, int | Literal['EchoTimedOut', 'ResponseTimedOut']]:
        """
        `lds addr` instruction. (opcode 0x0_)
        addr_width: address width (0=B; 1=W)  
        data_width: data width (0=B; 1=W)  
        * prefixing with `repeat` is supported by hardware, but omitted from this library
        """
        return super().load_direct(addr, addr_width, data_width)
    
    def store_direct(self, addr:int, data:int, addr_width:Literal[0,1]=1, data_width:Literal[0,1]=0) -> Tuple[bool, Optional[Literal['AddressNacked', 'DataNacked']]]:
        """
        `sts addr, val` instruction. (opcode 0x4_)
        addr_width: address width (0=B; 1=W)  
        data_width: data width (0=B; 1=W)  
        * prefixing with `repeat` is supported by hardware, but omitted from this library
        """
        return super().store_direct(addr, data, addr_width, data_width)