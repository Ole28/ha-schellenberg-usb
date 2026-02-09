import threading
from queue import Queue

import serial

from .commands import Command
from .devices import SenderDevice
from .message import OutgoingSchellenbergMessage, SchellenbergMessageReceived
from .settings import SETTINGS

QUEUE: Queue[OutgoingSchellenbergMessage] = Queue()
TRANSMITTER_LOCK = threading.Lock()
last_pairing_message: SchellenbergMessageReceived | None = None


def reader(ser: serial.Serial) -> None:
    while True:
        response = ser.readline().strip()
        if response:
            if response == b"t1":
                print("[SERIAL] transmitter lock")
                TRANSMITTER_LOCK.acquire(False)
                continue
            if response == b"t0":
                print("[SERIAL] transmitter unlock")
                TRANSMITTER_LOCK.release()
                continue
            if response == b"tE":
                raise RuntimeError("Transmitter error")
            try:
                message = SchellenbergMessageReceived.from_bytes(response)
                print(f"[SERIAL] Received message: {message}")
                if message.command == Command.ALLOW_PAIRING:
                    global last_pairing_message
                    last_pairing_message = message
            except ValueError as e:
                print(f"[SERIAL] Error parsing message: {e} ({response})")


def writer(ser: serial.Serial) -> None:
    while True:
        command = QUEUE.get(block=True)
        TRANSMITTER_LOCK.acquire(timeout=10.0)
        print(command, bytes(command))
        command.run(ser)
        TRANSMITTER_LOCK.acquire(timeout=10.0)
        command.post_run()
        TRANSMITTER_LOCK.release()


def stdin_reader() -> None:
    while True:
        user_input = input(
            f"Enter command ({', '.join(Command.__members__.keys())}):\n"
        ).strip()
        if user_input.upper() == Command.ALLOW_PAIRING.name:
            new_enumerator = input("New Enumerator in hex: ").strip()
            if (
                not new_enumerator
                or len(new_enumerator) > 2
                or last_pairing_message is None
            ):
                continue
            command = OutgoingSchellenbergMessage(
                enumerator=new_enumerator,
                num_retries=9,
                command=Command.ALLOW_PAIRING,
            )
            QUEUE.put(command)
        elif user_input in Command.__members__:
            if SETTINGS.self_sender is None:
                print("No self sender device found. Cannot send command.")
                continue
            available_devices = list(SETTINGS.self_sender.connected_devices)
            print(f"Available devices: {list(enumerate(available_devices))}")
            try:
                device_index = int(input("Device index: ").strip())
            except ValueError:
                print("Invalid device index.")
                continue
            if device_index < 0 or device_index >= len(available_devices):
                continue
            command = OutgoingSchellenbergMessage(
                enumerator=available_devices[device_index].enumerator,
                num_retries=9,
                command=Command[user_input.upper()],  # Convert to Command enum
            )
            QUEUE.put(command)
        else:
            print("Invalid command.")


def cli() -> None:
    with serial.Serial(
        "COM3", SETTINGS.baud_rate, timeout=SETTINGS.timeout
    ) as ser:
        ser.write(b"hello\n")
        print(f"Connected to {ser.name}")
        ser.write(b"!?\n")
        print(str(ser.readline().strip(), "ascii"))

        ser.write(b"sr\n")
        own_id = str(ser.readline().strip()[2:], "ascii")
        SETTINGS.self_sender_id = own_id
        SETTINGS.senders.add(SenderDevice(device_id=own_id, name="self"))
        print(f"{own_id=}")
        SETTINGS.save()

        readerThread = threading.Thread(
            target=reader, args=(ser,), daemon=True
        )
        readerThread.start()

        writerThread = threading.Thread(
            target=writer, args=(ser,), daemon=True
        )
        writerThread.start()

        stdin_reader()
