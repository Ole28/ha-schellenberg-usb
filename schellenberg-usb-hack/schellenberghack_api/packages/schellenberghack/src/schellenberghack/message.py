from dataclasses import dataclass
from enum import Enum
from typing import Literal

import serial

from .commands import Command
from .devices import Device, SenderDevice
from .settings import SETTINGS


class DeviceState(Enum):
    OPEN = "open"
    CLOSED = "closed"
    OPENING = "opening"
    CLOSING = "closing"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


@dataclass
class SchellenbergMessageReceived:
    prefix: Literal["ss"]
    sender: SenderDevice
    receiver: str  # hex
    command: Command
    counter: int
    local_counter: int
    signal_strength: int

    original_bytes: bytes | None = None

    def __str__(self) -> str:
        return (
            f"SchellenbergMessage(sender={self.sender.name or ""}"
            f" ({self.sender.device_id}), "
            f"receiver=0x{self.receiver}, "
            f"{self.command}, "
            f"cnt={self.counter}, lcnt={self.local_counter}, "
            f"lq={self.signal_strength}) "
            f"({self.original_bytes})"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "sender": {
                "device_id": self.sender.device_id,
                "name": self.sender.name,
            },
            "receiver": self.receiver,
            "command": self.command.name,
            "counter": self.counter,
            "local_counter": self.local_counter,
            "signal_strength": self.signal_strength,
        }

    @classmethod
    def from_bytes(cls, data: bytes) -> "SchellenbergMessageReceived":
        if len(data) != 20 or not data.startswith(b"ss"):
            raise ValueError(f"Invalid Schellenberg message format: {data}")

        receiver_enumerator = int(data[2:4], 16)
        device_id = int(data[4:10], 16)
        command_code = int(data[10:12], 16)
        counter = int(data[12:16], 16)
        local_counter = int(data[16:18], 16)
        signal_strength = int(data[18:20], 16)

        sender = SenderDevice.from_id(
            device_id=f"{device_id:06X}", create=True
        )
        SETTINGS.add_device(
            sender.device_id, Device(enumerator=f"{receiver_enumerator:02X}")
        )
        return cls(
            prefix="ss",
            sender=sender,
            receiver=f"{receiver_enumerator:02X}",
            command=Command.from_code(command_code),
            counter=counter,
            local_counter=local_counter,
            signal_strength=signal_strength,
            original_bytes=data,
        )


@dataclass
class OutgoingSchellenbergMessage:
    """
    ss 	    Schellenberg Prefix? 	Fixed
    A5 	    Device Enumerator 	    The id used by SenderDevice, identifing pair
    9 	    Numbers of Messages 	Send 9 Messages after each other. Can be 0-F
    01 	    Command
    0000 	Padding 	            Required.
    """

    enumerator: str  # hex
    command: Command
    num_retries: int = 9

    def __bytes__(self) -> bytes:
        return (
            f"ss{self.enumerator}{self.num_retries:X}"
            f"{self.command.value:02X}0000\n".encode(encoding="ascii")
        )

    def __str__(self) -> str:
        return (
            f"OutgoingSchellenbergCommand(0x{self.enumerator}, "
            f"num_retries={self.num_retries}, command={self.command})"
        )

    def pre_run(self) -> None: ...

    def run(self, ser: serial.Serial) -> None:
        ser.write(bytes(self))

    def post_run(self) -> None:
        if self.command in [Command.UP, Command.MANUAL_UP]:
            self.expected_state = DeviceState.OPEN
        elif self.command in [Command.DOWN, Command.MANUAL_DOWN]:
            self.expected_state = DeviceState.CLOSED
