from typing import Final

try:
    from komoe_devtools import Devtools
except ImportError:

    class Devtools:  # type: ignore[no-redef]
        are_available: Final[bool] = False
