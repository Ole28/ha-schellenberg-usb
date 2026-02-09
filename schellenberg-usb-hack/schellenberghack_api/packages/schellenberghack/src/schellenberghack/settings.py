import json
from pathlib import Path

from pydantic import BaseModel, field_serializer

from .devices import Device, SenderDevice


class Settings(BaseModel):
    baud_rate: int = 9600
    timeout: int = 10
    senders: set[SenderDevice] = set()
    self_sender_id: str | None = None

    @property
    def self_sender(self) -> SenderDevice | None:
        return next(
            filter(lambda s: s.device_id == self.self_sender_id, self.senders),
            None,
        )

    def get_sender_by_id(self, device_id: str) -> SenderDevice | None:
        return next(
            filter(lambda s: s.device_id == device_id, self.senders), None
        )

    def get_device_by_sender_and_enumerator(
        self, sender_id: str, enumerator: str
    ) -> Device | None:
        sender = self.get_sender_by_id(sender_id)
        if sender:
            return next(
                filter(
                    lambda d: d.enumerator == enumerator,
                    sender.connected_devices,
                ),
                None,
            )

    def add_device(self, sender_id: str, device: Device) -> None:
        sender = self.get_sender_by_id(sender_id)
        if sender:
            sender.connected_devices.add(device)
            self.save()

    def pair_device(self, enumerator: str, name: str | None = None) -> None:
        print(f"[PAIR] Pairing device with enumerator {enumerator}")
        if not self.self_sender:
            raise ValueError("Self sender device not initialized")
        self.self_sender.connected_devices.add(
            Device(enumerator=enumerator, name=name)
        )
        self.save()

    def remove_device(self, sender_id: str, enumerator: str) -> None:
        if sender := self.get_sender_by_id(sender_id):
            sender.connected_devices.remove(Device(enumerator=enumerator))
            self.save()

    def rename_sender(
        self, sender_id: str, new_name: str
    ) -> SenderDevice | None:
        sender = self.get_sender_by_id(sender_id)
        if sender:
            sender.name = new_name
            self.save()
        return sender

    def rename_receiver(
        self, sender_id: str, enumerator: str, new_name: str
    ) -> Device | None:
        device = self.get_device_by_sender_and_enumerator(
            sender_id, enumerator
        )
        if device:
            device.name = new_name
            self.save()
        return device

    @classmethod
    def from_file(cls, file_path: Path) -> "Settings":
        if not file_path.exists():
            return cls()
        with open(file_path, "r") as f:
            try:
                data = json.load(f)
                return cls(**data)
            except json.JSONDecodeError:
                return cls()

    def save(self) -> None:
        with open(file, "w") as f:
            json.dump(self.model_dump(mode="json"), f, indent=2)

    @field_serializer("senders")
    def serialize_senders(
        self, senders: set[SenderDevice]
    ) -> list[SenderDevice]:
        return sorted(
            senders,
            key=lambda s: (
                s.connected_devices,
                s.name if s.name else "",
                s.device_id,
            ),
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.baud_rate,
                self.timeout,
                frozenset(self.senders),
                self.self_sender,
            )
        )


file = Path("/data/settings.json")
file.touch()

SETTINGS = Settings.from_file(file)
