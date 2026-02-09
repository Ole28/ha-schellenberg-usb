from pydantic import BaseModel, field_validator


class Device(BaseModel):
    enumerator: str  # hex
    name: str | None = None

    @field_validator("enumerator")
    @classmethod
    def validate_enumerator(cls, value: str) -> str:
        if not (0 <= int(value, 16) <= 0xFF):
            raise ValueError("Enumerator must be between 0 and 255 (0xFF)")
        return value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Device):
            return super().__eq__(other)
        return other.enumerator == self.enumerator

    def __hash__(self) -> int:
        return hash(self.enumerator)


class SenderDevice(BaseModel):
    device_id: str  # hex between 0x0 and 0xFFFFFF
    name: str | None = None
    connected_devices: set[Device] = set()

    @classmethod
    def from_id(cls, device_id: str, create: bool = False) -> "SenderDevice":
        from .settings import SETTINGS

        existing_device = SETTINGS.get_sender_by_id(device_id)
        if existing_device:
            return existing_device
        if not create:
            raise ValueError(f"No device found with ID {device_id}")
        new = cls(device_id=device_id)
        SETTINGS.senders.add(new)
        SETTINGS.save()
        return new

    @field_validator("device_id")
    @classmethod
    def validate_device_id(cls, value: str) -> str:
        if not (0 <= int(value, 16) <= 0xFFFFFF):
            raise ValueError("Device ID must be between 0x0 and 0xFFFFFF")
        return value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SenderDevice):
            return super().__eq__(other)
        return other.device_id == self.device_id

    def __hash__(self) -> int:
        return hash(self.device_id)
