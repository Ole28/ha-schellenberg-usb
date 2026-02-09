from typing import List
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from schellenberghack import SETTINGS
from schellenberghack.commands import Command
from schellenberghack.devices import Device, SenderDevice
from schellenberghack.message import (OutgoingSchellenbergMessage,
                                      SchellenbergMessageReceived)
from serial import Serial

from .homeassistant import HomeAssistantWorker
from .worker import (
    ReceiveWorker,
    SendWorker,
    MockReceiveWorker,
    MockSendWorker,
    MOCK_MODE,
)

print("Starting Schellenberg API...")


async def fanout_received_messages():
    worker: ReceiveWorker = app.state.receive_worker
    ha_worker: HomeAssistantWorker = app.state.ha_worker
    clients: List[WebSocket] = app.state.websocket_clients
    while True:
        msg = await worker.receivedMessages.get()
        disconnected: List[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(msg.to_dict())
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            clients.remove(ws)

        await ha_worker.handle_received_message(msg)


async def mqtt_command_forwarder():
    ha_worker: HomeAssistantWorker = app.state.ha_worker
    send_worker: SendWorker = app.state.send_worker
    while True:
        command = await ha_worker.get_send_queue().get()
        await send_worker.send(command)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if MOCK_MODE:
        print("=" * 60)
        print("RUNNING IN MOCK MODE - No serial connection required")
        print("=" * 60)

        # Mock serial setup
        own_id = "ABCDEF"
        print(f"[MOCK] Using mock device ID: {own_id}")

        SETTINGS.self_sender_id = own_id
        SETTINGS.senders.add(SenderDevice(device_id=own_id, name="self"))

        websocket_clients: set[WebSocket] = set()
        app.state.websocket_clients = websocket_clients

        # Use mock workers
        app.state.send_worker = MockSendWorker()
        app.state.receive_worker = MockReceiveWorker()
        app.state.ha_worker = HomeAssistantWorker(
            mqtt_host=os.getenv("MQTT_HOST", "core-mosquitto"),
            mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
            mqtt_user=os.getenv("MQTT_USER"),
            mqtt_password=os.getenv("MQTT_PASSWORD"),
        )

        app.state.send_worker.start()
        app.state.receive_worker.start()
        app.state.ha_worker.start()

        asyncio.create_task(fanout_received_messages())
        asyncio.create_task(mqtt_command_forwarder())

        async def mock_open_close_shutters():
            """Mock task to simulate opening and closing shutters."""
            while True:
                await asyncio.sleep(5)
                print("[MOCK] Simulating shutter open command")
                await app.state.receive_worker.simulate_incoming_message(
                    SchellenbergMessageReceived.from_bytes(
                        b"ssDEABCDEF0100bb20CB"
                    )
                )
                await asyncio.sleep(5)
                print("[MOCK] Simulating shutter close command")
                await app.state.receive_worker.simulate_incoming_message(
                    SchellenbergMessageReceived.from_bytes(
                        b"ssDEFEDCBA0200bc02CB"
                    )
                )
        asyncio.create_task(mock_open_close_shutters())

        yield

        await app.state.ha_worker.exit()
        await app.state.send_worker.exit()
        await app.state.receive_worker.exit()
        SETTINGS.save()
    else:
        # Real serial connection
        serial_port = os.getenv("SERIAL")
        if not serial_port:
            raise ValueError("SERIAL_PORT environment variable not set")
        try:
            ser = Serial(
                serial_port, SETTINGS.baud_rate, timeout=SETTINGS.timeout
            )
        except Exception as e:
            print(f"[SERIAL] Error opening serial port \"{serial_port}\": {e}")
            return
        ser.write(b"hello\n")
        print(f"[SERIAL] Connected to {ser.name}")
        ser.write(b"!?\n")
        print(str(ser.readline().strip(), "ascii"))

        ser.write(b"sr\n")
        own_id = str(ser.readline().strip(), "ascii")[2:]
        print(f"{own_id=}")

        SETTINGS.self_sender_id = own_id
        SETTINGS.senders.add(SenderDevice(device_id=own_id, name="self"))

        websocket_clients: set[WebSocket] = set()
        app.state.websocket_clients = websocket_clients

        app.state.send_worker = SendWorker(ser)
        app.state.receive_worker = ReceiveWorker(ser)
        app.state.ha_worker = HomeAssistantWorker(
            mqtt_host=os.getenv("MQTT_HOST", "core-mosquitto"),
            mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
            mqtt_user=os.getenv("MQTT_USER"),
            mqtt_password=os.getenv("MQTT_PASSWORD"),
        )

        app.state.send_worker.start()
        app.state.receive_worker.start()
        app.state.ha_worker.start()

        asyncio.create_task(fanout_received_messages())
        asyncio.create_task(mqtt_command_forwarder())

        yield

        await app.state.ha_worker.exit()
        await app.state.send_worker.exit()
        await app.state.receive_worker.exit()
        ser.close()
        SETTINGS.save()


app = FastAPI(lifespan=lifespan)


class AllDevicesResponse(BaseModel):
    senders: set[SenderDevice]
    self_sender_id: str


@app.get("/health")
def health_check():
    print("Health check received")
    return {"status": "ok"}


@app.get("/api/devices/all")
def get_devices() -> AllDevicesResponse:
    if SETTINGS.self_sender_id is None:
        raise ValueError("Self sender ID is not set")
    return AllDevicesResponse(
        senders=SETTINGS.senders, self_sender_id=SETTINGS.self_sender_id
    )


@app.get("/api/devices/paired")
def get_paired_devices() -> SenderDevice | None:
    return SETTINGS.self_sender


@app.get("/api/devices/specific/{sender_id}/{enumerator}")
def device(sender_id: str, enumerator: str) -> Device | None:
    return SETTINGS.get_device_by_sender_and_enumerator(sender_id, enumerator)


@app.post("/api/devices/specific/{sender_id}/rename")
def rename_sender(sender_id: str, new_name: str) -> SenderDevice | None:
    return SETTINGS.rename_sender(sender_id, new_name)


@app.post("/api/devices/specific/{sender_id}/{enumerator}/rename")
def rename_device(
    sender_id: str, enumerator: str, new_name: str
) -> Device | None:
    return SETTINGS.rename_receiver(sender_id, enumerator, new_name)


@app.post("/api/devices/specific/{sender_id}/{enumerator}/remove")
def remove_device(sender_id: str, enumerator: str) -> None:
    SETTINGS.remove_device(sender_id, enumerator)


@app.post("/api/devices/specific/{sender_id}/{enumerator}/command")
async def send_command(sender_id: str,
                       enumerator: str,
                       command: str) -> dict[str, str]:
    """Send a command to a specific device."""
    try:
        # Parse command string to Command enum
        cmd = Command[command.upper()]
    except KeyError:
        return {
            "status": "error",
            "message": f"Invalid command: {command}."
            f" Valid commands: {[c.name for c in Command]}",
        }

    device = SETTINGS.get_device_by_sender_and_enumerator(sender_id,
                                                          enumerator)
    if not device:
        return {
            "status": "error",
            "message": f"Device not found: {sender_id}/{enumerator}",
        }

    # Send command
    send_worker: SendWorker = app.state.send_worker
    await send_worker.send(
        OutgoingSchellenbergMessage(enumerator=enumerator, command=cmd)
    )

    return {
        "status": "success",
        "message": f"Command {command} sent to {sender_id}/{enumerator}",
    }


@app.post("/api/devices/specific/{receiver_id}/{enumerator}/pair")
async def pair_device(receiver_id: str, enumerator: str) -> Device | None:
    send_worker: SendWorker = app.state.send_worker
    receive_worker: ReceiveWorker = app.state.receive_worker
    pairing_message = await receive_worker.wait_for_pairing_message(
        receiver_id
    )
    if not pairing_message:
        return None
    await send_worker.send(
        OutgoingSchellenbergMessage(
            enumerator=enumerator, command=Command.ALLOW_PAIRING
        )
    )
    device = next(
        filter(
            lambda d: d.enumerator == pairing_message.receiver,
            pairing_message.sender.connected_devices,
        ),
        None,
    )
    SETTINGS.pair_device(enumerator, device.name if device else None)

    # Publish autodiscovery config for the new device
    ha_worker: HomeAssistantWorker = app.state.ha_worker
    new_device = SETTINGS.get_device_by_sender_and_enumerator(
        receiver_id, enumerator
    )
    if new_device and new_device.name and SETTINGS.self_sender:
        await ha_worker.publish_discovery_config(
            SETTINGS.self_sender,
            new_device.name
        )

    return SETTINGS.get_device_by_sender_and_enumerator(
        receiver_id, enumerator
    )


@app.post("/api/homeassistant/republish")
async def republish_ha_configs():
    """Republish all Home Assistant autodiscovery configurations."""
    ha_worker: HomeAssistantWorker = app.state.ha_worker
    await ha_worker.publish_all_discovery_configs()
    return {"status": "success", "message": "Autodiscovery republished"}


@app.websocket("/api/devices/events")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    print(f"[WebSocket] Client connected. Total clients: "
          f"{len(app.state.websocket_clients) + 1}", flush=True)

    app.state.websocket_clients.add(websocket)

    try:
        # Keep connection alive and wait for client disconnect
        while True:
            # Receive to detect client disconnect, but ignore
            await websocket.receive_text()
    except WebSocketDisconnect:
        print("[WebSocket] Client disconnected", flush=True)
    except Exception as e:
        print(f"[WebSocket] Error: {e}", flush=True)
    finally:
        app.state.websocket_clients.discard(websocket)
        print(f"[WebSocket] Client removed. Total clients: "
              f"{len(app.state.websocket_clients)}", flush=True)
