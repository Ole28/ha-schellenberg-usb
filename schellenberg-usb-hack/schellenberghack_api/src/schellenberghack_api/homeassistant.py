import asyncio
import json
import os
import re
from asyncio import Event, Queue
from typing import Any

import aiomqtt
from schellenberghack import SETTINGS
from schellenberghack.commands import Command
from schellenberghack.devices import Device, SenderDevice
from schellenberghack.message import (
    DeviceState,
    OutgoingSchellenbergMessage,
    SchellenbergMessageReceived,
)


class HomeAssistantWorker:
    """
    Worker that handles MQTT communication with Home Assistant.
    Publishes autodiscovery messages for all paired devices
    and handles commands.
    """

    def __init__(
        self,
        mqtt_host: str = "core-mosquitto",
        mqtt_port: int = 1883,
        mqtt_user: str | None = None,
        mqtt_password: str | None = None,
    ):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
        self.exit_event = Event()
        self.task = None
        self.client: aiomqtt.Client | None = None
        self.send_queue: Queue[OutgoingSchellenbergMessage] = Queue()
        # Map device_name (slug) to list of (sender_id, enumerator) tuples
        self.device_mapping: dict[str, list[tuple[str, str]]] = {}
        self.device_states: dict[str, DeviceState] = {}

    def _get_discovery_prefix(self) -> str:
        """Get the Home Assistant discovery prefix."""
        return os.getenv("HA_MQTT_DISCOVERY_PREFIX", "homeassistant")

    def _make_slug(self, text: str) -> str:
        slug = text.lower()
        slug = (slug.replace(" ", "-").replace("_", "-").replace(".", "-")
                    .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue"))
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("-")
        return slug or "unnamed-device"

    def _get_device_name(self, device: Device) -> str:
        if device.name:
            return self._make_slug(device.name)
        return f"device-{device.enumerator}"

    def _get_unique_id(self, sender_id: str, enumerator: str) -> str:
        return f"schellenberg_{sender_id}_{enumerator}"

    async def publish_discovery_config(
        self, sender: SenderDevice, device_name: str
    ):
        """Publish MQTT autodiscovery config for a single device."""
        if not self.client:
            return

        discovery_topic = (
            f"{self._get_discovery_prefix()}/cover/{device_name}/config"
        )

        # Command and state topics
        command_topic = f"schellenberg/{device_name}/set"
        state_topic = f"schellenberg/{device_name}/state"
        availability_topic = "schellenberg/availability"

        config: dict[str, Any] = {
            "name": device_name,
            "unique_id": device_name,
            "command_topic": command_topic,
            "state_topic": state_topic,
            "availability_topic": availability_topic,
            "payload_open": "OPEN",
            "payload_close": "CLOSE",
            "payload_stop": "STOP",
            "state_open": "open",
            "state_closed": "closed",
            "state_opening": "opening",
            "state_closing": "closing",
            "state_stopped": "stopped",
            "state_unknown": "unknown",
            "optimistic": False,
            "device": {
                "identifiers": [device_name],
                "name": device_name,
                "manufacturer": "Schellenberg",
                "model": "Cover Device",
                "sw_version": "1.0.0",
                "via_device": f"schellenberg_usb_{sender.device_id}",
            },
        }

        await self.client.publish(
            discovery_topic,
            payload=json.dumps(config),
            qos=1,
            retain=True,
        )
        self.device_states[device_name] = DeviceState.UNKNOWN

        print(f"[MQTT] Published discovery config for {device_name}")

    async def publish_all_discovery_configs(self):
        """Publish discovery configs for all paired devices."""
        if not SETTINGS.self_sender:
            print("[MQTT] No self sender configured, skipping discovery")
            return

        for device in SETTINGS.self_sender.connected_devices:
            await self.publish_discovery_config(
                SETTINGS.self_sender,
                self._get_device_name(device)
            )

        print(
            f"[MQTT] Published "
            f"{len(SETTINGS.self_sender.connected_devices)} devices"
        )

    def _update_device_mapping(self):
        self.device_mapping.clear()
        for sender in SETTINGS.senders:
            for device in sender.connected_devices:
                device_name = self._get_device_name(device)
                if device_name not in self.device_mapping:
                    self.device_mapping[device_name] = []
                self.device_mapping[device_name].append(
                    (sender.device_id, device.enumerator)
                )

    async def _handle_command(self, message: aiomqtt.Message):
        """Handle incoming MQTT commands."""
        if not self.client:
            raise RuntimeError("[HANDLE_COMMAND] MQTT client not initialized")
        self._update_device_mapping()

        try:
            topic = str(message.topic)
            payload = message.payload.decode()

            if not topic.startswith("schellenberg/") or not topic.endswith(
                "/set"
            ):
                return

            device_name = topic.split("/")[1]
            print(device_name, self.device_mapping)

            if device_name not in self.device_mapping:
                print(f"[MQTT] Unknown device name: {device_name}")
                return

            devices = self.device_mapping[device_name]

            command_map = {
                "OPEN": Command.UP,
                "CLOSE": Command.DOWN,
                "STOP": Command.STOP,
            }

            if payload not in command_map:
                print(f"[MQTT] Unknown command: {payload}")
                return

            command = command_map[payload]

            new_state: DeviceState = DeviceState.UNKNOWN

            state_topic = f"schellenberg/{device_name}/state"
            if payload == "OPEN":
                new_state = DeviceState.OPENING
            elif payload == "CLOSE":
                new_state = DeviceState.CLOSING
            elif payload == "STOP":
                new_state = DeviceState.STOPPED

            await self.client.publish(topic=state_topic,
                                      payload=new_state.value,
                                      qos=1, retain=True)
            self.device_states[device_name] = new_state

            for sender_id, enumerator in devices:
                if not SETTINGS.self_sender \
                        or SETTINGS.self_sender.device_id != sender_id:
                    continue

                def state_callback(state: DeviceState):
                    async def delayed_callback():
                        await asyncio.sleep(5)
                        await self.update_device_state(device_name, state)
                    asyncio.create_task(delayed_callback())

                msg = OutgoingSchellenbergMessage(
                    enumerator=enumerator, command=command,
                    state_callback=state_callback
                )
                await self.send_queue.put(msg)
                print(
                    f"[MQTT] Queued command {command} for "
                    f"device {sender_id}/{enumerator} (key: {device_name})"
                )

        except Exception as e:
            print(f"[MQTT] Error handling command: {e}")

    async def update_device_state(self, device_name: str, state: DeviceState):
        if not self.client:
            raise RuntimeError("[UPDATE_DEVICE_STATE] MQTT "
                               "client not initialized")

        state_topic = f"schellenberg/{device_name}/state"

        await self.client.publish(
            state_topic, payload=state.value, qos=1, retain=True
        )
        self.device_states[device_name] = state
        print(f"[MQTT] Updated {device_name} state to {state}")

    async def _extract_device_state(
        self, message: SchellenbergMessageReceived
    ):
        """Update device state based on received messages."""
        if not self.client:
            raise RuntimeError("[UPDATE_DEVICE_STATE] MQTT "
                               "client not initialized")

        device_tuple = (message.sender.device_id, message.receiver)
        device_name = next((name for name, devices
                            in self.device_mapping.items()
                            if device_tuple in devices
                            ), None)
        if not device_name:
            return

        if message.command in [Command.UP, Command.MANUAL_UP]:
            state = DeviceState.OPENING
        elif message.command in [Command.DOWN, Command.MANUAL_DOWN]:
            state = DeviceState.CLOSING
        elif message.command == Command.STOP:
            state = DeviceState.STOPPED
        else:
            return

        if self.device_states.get(device_name) != state:
            self.device_states[device_name] = state
            await self.update_device_state(device_name, state)

    async def _mqtt_loop(self):
        """Main MQTT event loop."""
        will = aiomqtt.Will("schellenberg/availability",
                            payload="offline",
                            qos=1,
                            retain=True)
        while not self.exit_event.is_set():
            try:
                async with aiomqtt.Client(
                        hostname=self.mqtt_host,
                        port=self.mqtt_port,
                        username=self.mqtt_user,
                        password=self.mqtt_password,
                        will=will
                        ) as client:
                    self.client = client

                    await client.publish(
                        "schellenberg/availability",
                        payload="online",
                        qos=1,
                        retain=True,
                    )

                    await self.publish_all_discovery_configs()
                    await client.subscribe("schellenberg/+/set")
                    print("[MQTT] Subscribed to command topics")

                    async for message in client.messages:
                        if self.exit_event.is_set():
                            break
                        await self._handle_command(message)

            except aiomqtt.MqttError as e:
                print(f"[MQTT] MQTT error: {e}. Reconnecting in 5 seconds...")
                print(f"[MQTT] Ensure the MQTT broker is running and "
                      f"accessible at {self.mqtt_host}:{self.mqtt_port}")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"[MQTT] Unexpected error in MQTT loop: {e}")
                await asyncio.sleep(5)

    def start(self):
        """Start the Home Assistant worker."""
        self.task = asyncio.create_task(self._mqtt_loop())
        print("[MQTT] Home Assistant MQTT worker started")

    async def exit(self):
        """Stop the Home Assistant worker."""
        self.exit_event.set()

        # Publish offline status
        if self.client:
            try:
                await self.client.publish(
                    "schellenberg/availability",
                    payload="offline",
                    qos=1,
                    retain=True,
                )
            except Exception:
                pass

        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def handle_received_message(
        self, message: SchellenbergMessageReceived
    ):
        """Handle a message received from the Schellenberg device."""
        await self._extract_device_state(message)

    def get_send_queue(self) -> Queue[OutgoingSchellenbergMessage]:
        """Get the queue for sending commands to devices."""
        return self.send_queue
