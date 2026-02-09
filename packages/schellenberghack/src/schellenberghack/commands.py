# 0x00 Stop
# 0x01 Up
# 0x02 Down
# 0x1A Window Handle Position 0° 	Sensor status with Device Enumerator 0x14
# 0x1B Window Handle Position 90° 	Sensor status with Device Enumerator 0x14
# 0x3B Window Handle Position 180° 	Sensor status with Device Enumerator 0x14
# 0x40 Allow Pairing 	Make the selected device listen to a new Remotes ID
# 0x41 Manual Up 	As long as the button is held
# 0x42 Manual Down 	As long as the button is held
# 0x60 Pair / Change Direction 	Pair with my Device ID / Change your Direction
# 0x61 Set upper endpoint
# 0x62 Set lower endpoint

from enum import Enum


class Command(Enum):
    STOP = 0x00
    UP = 0x01
    DOWN = 0x02
    WINDOW_HANDLE_POSITION_0 = 0x1A
    WINDOW_HANDLE_POSITION_90 = 0x1B
    WINDOW_HANDLE_POSITION_180 = 0x3B
    ALLOW_PAIRING = 0x40
    MANUAL_UP = 0x41
    MANUAL_DOWN = 0x42
    PAIR_CHANGE_DIRECTION = 0x60
    SET_UPPER_ENDPOINT = 0x61
    SET_LOWER_ENDPOINT = 0x62

    @classmethod
    def from_code(cls, code: int) -> "Command":
        if code not in cls._value2member_map_:
            raise ValueError(f"Unknown command code: 0x{code:02X}")
        return cls(code)

    def __repr__(self) -> str:
        return f"Command.{self.name} (0x{self.value:02X})"
