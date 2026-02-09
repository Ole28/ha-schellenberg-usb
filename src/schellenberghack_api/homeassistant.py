import asyncio
import json
import os
from asyncio import Event, Queue

import aiomqtt
from schellenberghack import SETTINGS
from schellenberghack.commands import Command
from schellenberghack.devices import Device, SenderDevice
from schellenberghack.message import (
    OutgoingSchellenbergMessage,
    SchellenbergMessageReceived,
)


class HomeAssistantWorker:
    """
    Worker that handles MQTT communication with Home Assistant.
    Publishes autodiscovery messages for all paired devices and handles commands.
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
        self.device_states: dict[str, str] = {}  # device_key -> state
        self.send_queue: Queue[OutgoingSchellenbergMessage] = Queue()

    def _get_discovery_prefix(self) -> str:
        """Get the Home Assistant discovery prefix."""
        return os.getenv("HA_MQTT_DISCOVERY_PREFIX", "homeassistant")

    def _get_device_key(self, sender_id: str, enumerator: str) -> str:
        """Generate a unique device key."""
        return f"{sender_id}_{enumerator}"

    def _get_unique_id(self, sender_id: str, enumerator: str) -> str:
        """Generate a unique ID for Home Assistant."""
        return f"schellenberg_{sender_id}_{enumerator}"

    def _get_device_name(
        self, sender: SenderDevice, device: Device
    ) -> str:
        """Get a friendly name for the device."""
        if device.name:
            return device.name
        sender_name = sender.name or sender.device_id
        return f"Schellenberg {sender_name} {device.enumerator}"

    async def _publish_discovery_config(
        self, sender: SenderDevice, device: Device
    ):
        """Publish MQTT autodiscovery config for a single device."""
        if not self.client:
            return

        unique_id = self._get_unique_id(sender.device_id, device.enumerator)
        device_key = self._get_device_key(sender.device_id, device.enumerator)

        # Discovery topic for cover platform
        discovery_topic = (
            f"{self._get_discovery_prefix()}/cover/{unique_id}/config"
        )

        # Command and state topics
        command_topic = f"schellenberg/{device_key}/set"
        state_topic = f"schellenberg/{device_key}/state"
        availability_topic = "schellenberg/availability"

        config = {
            "name": self._get_device_name(sender, device),
            "unique_id": unique_id,
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
            "optimistic": False,
            "device": {
                "identifiers": [unique_id],
                "name": self._get_device_name(sender, device),
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
        print(f"[MQTT] Published discovery config for {device_key}")

        # Initialize device state
        self.device_states[device_key] = "stopped"
        await self.client.publish(
            state_topic, payload="stopped", qos=1, retain=True
        )

    async def _publish_all_discovery_configs(self):
        """Publish discovery configs for all paired devices."""
        if not SETTINGS.self_sender:
            print("[MQTT] No self sender configured, skipping discovery")
            return

        for device in SETTINGS.self_sender.connected_devices:
            await self._publish_discovery_config(
                SETTINGS.self_sender, device
            )

        print(
            f"[MQTT] Published {len(SETTINGS.self_sender.connected_devices)} device configs"
        )

    async def _handle_command(self, message: aiomqtt.Message):
        """Handle incoming MQTT commands."""
        try:
            topic = str(message.topic)
            payload = message.payload.decode()

            # Extract device info from topic: schellenberg/{sender_id}_{enumerator}/set
            if not topic.startswith("schellenberg/") or not topic.endswith(
                "/set"
            ):
                return

            device_key = topic.split("/")[1]
            sender_id, enumerator = device_key.rsplit("_", 1)

            # Map command to Schellenberg command
            command_map = {
                "OPEN": Command.UP,
                "CLOSE": Command.DOWN,
                "STOP": Command.STOP,
            }

            if payload not in command_map:
                print(f"[MQTT] Unknown command: {payload}")
                return

            command = command_map[payload]

            # Update state to opening/closing
            state_topic = f"schellenberg/{device_key}/state"
            if payload == "OPEN":
                await self.client.publish(
                    state_topic, payload="opening", qos=1, retain=True
                )
                self.device_states[device_key] = "opening"
            elif payload == "CLOSE":
                await self.client.publish(
                    state_topic, payload="closing", qos=1, retain=True
                )
                self.device_states[device_key] = "closing"
            elif payload == "STOP":
                await self.client.publish(
                    state_topic, payload="stopped", qos=1, retain=True
                )
                self.device_states[device_key] = "stopped"

            # Queue the command to be sent
            msg = OutgoingSchellenbergMessage(
                enumerator=enumerator, command=command
            )
            await self.send_queue.put(msg)
            print(
                f"[MQTT] Queued command {command} for device {sender_id}/{enumerator}"
            )

        except Exception as e:
            print(f"[MQTT] Error handling command: {e}")

    async def _update_device_state(
        self, message: SchellenbergMessageReceived
    ):
        """Update device state based on received messages."""
        if not self.client:
            return

        device_key = self._get_device_key(
            message.sender.device_id, message.receiver
        )
        state_topic = f"schellenberg/{device_key}/state"

        # Map commands to states
        if message.command in [Command.UP, Command.MANUAL_UP]:
            state = "opening"
        elif message.command in [Command.DOWN, Command.MANUAL_DOWN]:
            state = "closing"
        elif message.command == Command.STOP:
            # Determine if stopped in open or closed position
            # For now, just mark as stopped
            state = "stopped"
        else:
            return

        if self.device_states.get(device_key) != state:
            self.device_states[device_key] = state
            await self.client.publish(
                state_topic, payload=state, qos=1, retain=True
            )
            print(f"[MQTT] Updated {device_key} state to {state}")

    async def _mqtt_loop(self):
        """Main MQTT event loop."""
        while not self.exit_event.is_set():
            try:
                # Connect to MQTT broker
                client_kwargs = {
                    "hostname": self.mqtt_host,
                    "port": self.mqtt_port,
                }
                if self.mqtt_user and self.mqtt_password:
                    client_kwargs["username"] = self.mqtt_user
                    client_kwargs["password"] = self.mqtt_password

                async with aiomqtt.Client(**client_kwargs) as client:
                    self.client = client

                    # Publish availability
                    await client.publish(
                        "schellenberg/availability",
                        payload="online",
                        qos=1,
                        retain=True,
                    )

                    # Publish all discovery configs
                    await self._publish_all_discovery_configs()

                    # Subscribe to command topics
                    await client.subscribe("schellenberg/+/set")
                    print("[MQTT] Subscribed to command topics")

                    # Listen for messages
                    async for message in client.messages:
                        if self.exit_event.is_set():
                            break
                        await self._handle_command(message)

            except aiomqtt.MqttError as e:
                print(f"[MQTT] MQTT error: {e}. Reconnecting in 5 seconds...")
                print(f"[MQTT] Ensure the MQTT broker is running and accessible at {self.mqtt_host}:{self.mqtt_port}")
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
        await self._update_device_state(message)

    def get_send_queue(self) -> Queue[OutgoingSchellenbergMessage]:
        """Get the queue for sending commands to devices."""
        return self.send_queue
