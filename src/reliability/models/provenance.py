from enum import Enum


class DataProvenance(str, Enum):
    REAL_OPERATIONAL = "REAL_OPERATIONAL"
    PUBLIC_PROXY = "PUBLIC_PROXY"
    SEMI_SYNTHETIC = "SEMI_SYNTHETIC"
    SYNTHETIC = "SYNTHETIC"


__all__ = ["DataProvenance"]
