
from enum import Enum
class OperationType(Enum):
    PRODUCTION = "Production"
    QC = "QC"
    ACTIVATION = "Activation"
    SWITCH = "Switch"
    UNLINK_LINK = "Unlink Link"
    UNLINK = "Unlink"
    COUNT = "Count"