import asyncio
import json
from asyncio import Queue
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel
from schellenberghack import SETTINGS
from schellenberghack.commands import Command
from schellenberghack.devices import Device, SenderDevice
from schellenberghack.message import (
    OutgoingSchellenbergMessage,
    SchellenbergMessageReceived,
)
from serial import Serial
from sse_starlette import EventSourceResponse, ServerSentEvent

from .worker import ReceiveWorker, SendWorker

print("Starting Schellenberg API...")


async def fanout():
    worker: ReceiveWorker = app.state.receive_worker
    while True:
        msg = await worker.receivedMessages.get()
        for client in app.state.clients:
            await client.put(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ser = Serial(
        SETTINGS.serial_port, SETTINGS.baud_rate, timeout=SETTINGS.timeout
    )
    ser.write(b"hello\n")
    print(f"Connected to {ser.name}")
    ser.write(b"!?\n")
    print(str(ser.readline().strip(), "ascii"))

    ser.write(b"sr\n")
    own_id = str(ser.readline().strip(), "ascii")[2:]
    print(f"{own_id=}")

    SETTINGS.self_sender_id = own_id
    SETTINGS.senders.add(SenderDevice(device_id=own_id, name="self"))

    clients: set[Queue[SchellenbergMessageReceived]] = set()
    app.state.clients = clients

    app.state.send_worker = SendWorker(ser)
    app.state.receive_worker = ReceiveWorker(ser)
    app.state.send_worker.start()
    app.state.receive_worker.start()
    asyncio.create_task(fanout())

    yield

    await app.state.send_worker.exit()
    await app.state.receive_worker.exit()
    ser.close()
    SETTINGS.save()


app = FastAPI(lifespan=lifespan)


class AllDevicesResponse(BaseModel):
    senders: set[SenderDevice]
    self_sender_id: str


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
    return SETTINGS.get_device_by_sender_and_enumerator(
        receiver_id, enumerator
    )


@app.get("/api/devices/events")
async def usage_stream():
    clients: set[Queue[SchellenbergMessageReceived]] = app.state.clients

    client_queue: Queue[SchellenbergMessageReceived] = Queue()
    clients.add(client_queue)

    async def generator():
        try:
            while True:
                message = await client_queue.get()
                yield ServerSentEvent(json.dumps(message.to_dict()))
        finally:
            clients.remove(client_queue)

    return EventSourceResponse(generator())
