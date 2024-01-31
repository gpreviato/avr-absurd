from .updirev3 import UpdiRev3, UpdiException
from .updicompat import UpdiRev1, UpdiRev2

KEY_NVMPROG = b'NVMProg '
KEY_NVMERASE = b'NVMErase'
KEY_NVMUSERROW = b'NVMUs&te'
KEY_OCD = b'OCD     '
WIDTH_BYTE = 0
WIDTH_WORD = 1
WIDTH_3BYTE = 2
PTR_NOCHANGE = 0
PTR_INCREMENT = 1
PTR_DIRECT = 2
PTR_DECREMENT = 3