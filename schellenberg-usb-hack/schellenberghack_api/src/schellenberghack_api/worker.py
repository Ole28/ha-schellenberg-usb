import asyncio
import os
from asyncio import Event, Lock, Queue

from schellenberghack.commands import Command
from schellenberghack.message import (
    OutgoingSchellenbergMessage,
    SchellenbergMessageReceived,
)
from serial import Serial

transmitterLock = Lock()
finished_transmission = Event()

# Mock mode flag
MOCK_MODE = os.getenv("MOCK_SERIAL", "false").lower() in ("true", "1", "yes")


class SendWorker:
    def __init__(self, serial: Serial):
        self.ser = serial
        self.exit_event = Event()
        self.queue: Queue[OutgoingSchellenbergMessage] = Queue()
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self._run())

    async def _run(self):
        try:
            while self.ser.is_open and not self.exit_event.is_set():
                message = await self.queue.get()
                message.pre_run()
                try:
                    async with asyncio.timeout(10):
                        async with transmitterLock:
                            message.run(self.ser)
                            try:
                                async with asyncio.timeout(10):
                                    await finished_transmission.wait()
                            finally:
                                finished_transmission.clear()
                            message.post_run()
                except asyncio.TimeoutError:
                    print("Timeout in SendWorker")
        except asyncio.CancelledError:
            print("SendWorker cancelled")
            raise

    async def send(self, message: OutgoingSchellenbergMessage):
        await self.queue.put(message)

    async def exit(self):
        self.exit_event.set()
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass


class ReceiveWorker:
    def __init__(self, serial: Serial):
        self.ser = serial
        self.pairing_message_received = Event()
        self.last_pairing_message: SchellenbergMessageReceived | None = None
        self.receivedMessages: Queue[SchellenbergMessageReceived] = Queue()
        self.exit_event = Event()
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self._run())

    async def _run(self):
        loop = asyncio.get_event_loop()
        try:
            while self.ser.is_open and not self.exit_event.is_set():
                try:
                    response = await loop.run_in_executor(
                        None, lambda: self.ser.readline().strip()
                    )
                except Exception:
                    continue
                if response:
                    if response == b"t1":
                        print("transmitter lock")
                        if not transmitterLock.locked():
                            await transmitterLock.acquire()
                        continue
                    if response == b"t0":
                        print("transmitter unlock")
                        finished_transmission.set()
                        continue
                    if response == b"tE":
                        raise RuntimeError("Transmitter error")
                    try:
                        message = SchellenbergMessageReceived.from_bytes(
                            response
                        )
                        await self.receivedMessages.put(message)
                        print(message)
                        if message.command == Command.ALLOW_PAIRING:
                            self.last_pairing_message = message
                            self.pairing_message_received.set()
                    except ValueError as e:
                        print(f"Error parsing message: {e} ({response})")
        except asyncio.CancelledError:
            print("ReceiveWorker cancelled")
            raise

    async def wait_for_pairing_message(
        self, device_id: str, timeout: float = 10
    ) -> SchellenbergMessageReceived | None:
        self.pairing_message_received.clear()
        print("Waiting for pairing message...")
        while True:
            try:
                async with asyncio.timeout(timeout):
                    await self.pairing_message_received.wait()
            except asyncio.TimeoutError:
                print("Timeout waiting for pairing message.")
                return None
            except KeyboardInterrupt:
                return None
            await asyncio.sleep(1)  # wait for finished sending
            if self.last_pairing_message:
                if self.last_pairing_message.sender.device_id != device_id:
                    print(
                        f"Received pairing message from unexpected device "
                        f"{self.last_pairing_message.sender.device_id}, "
                        f"expected {device_id}. Ignoring."
                    )
                    self.pairing_message_received.clear()
                    continue
            print("Pairing message received!")
            self.pairing_message_received.clear()
            return self.last_pairing_message

    async def exit(self):
        self.exit_event.set()
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass


class MockSendWorker:
    """Mock SendWorker for development without serial connection."""

    def __init__(self, serial=None):
        self.ser = serial
        self.exit_event = Event()
        self.queue: Queue[OutgoingSchellenbergMessage] = Queue()
        self.task = None
        print("MockSendWorker initialized (no serial connection required)")

    def start(self):
        self.task = asyncio.create_task(self._run())

    async def _run(self):
        try:
            while not self.exit_event.is_set():
                message = await self.queue.get()
                message.pre_run()
                print(f"[MOCK] Would send message: {message}")

                # Simulate transmission lock and completion
                async with asyncio.timeout(1):
                    async with transmitterLock:
                        # Simulate sending without actual serial
                        await asyncio.sleep(0.1)  # Simulate transmission delay
                        finished_transmission.set()
                        await asyncio.sleep(0.1)
                        finished_transmission.clear()
                        message.post_run()
                        print(f"[MOCK] Message sent successfully")
        except asyncio.CancelledError:
            print("MockSendWorker cancelled")
            raise

    async def send(self, message: OutgoingSchellenbergMessage):
        await self.queue.put(message)

    async def exit(self):
        self.exit_event.set()
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass


class MockReceiveWorker:
    """Mock ReceiveWorker for development without serial connection."""

    def __init__(self, serial=None):
        self.ser = serial
        self.pairing_message_received = Event()
        self.last_pairing_message: SchellenbergMessageReceived | None = None
        self.receivedMessages: Queue[SchellenbergMessageReceived] = Queue()
        self.exit_event = Event()
        self.task = None
        print("MockReceiveWorker initialized (no serial connection required)")

    def start(self):
        self.task = asyncio.create_task(self._run())

    async def _run(self):
        """Simulate receiving messages periodically."""
        try:
            while not self.exit_event.is_set():
                # Just wait, don't generate fake messages unless needed
                # This allows manual testing through the API
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("MockReceiveWorker cancelled")
            raise

    async def simulate_incoming_message(self, message: SchellenbergMessageReceived):
        """Simulate an incoming message from a device."""
        await self.receivedMessages.put(message)
        print(f"[MOCK] Simulated incoming message: {message}")
        if message.command == Command.ALLOW_PAIRING:
            self.last_pairing_message = message
            self.pairing_message_received.set()

    async def wait_for_pairing_message(
        self, device_id: str, timeout: float = 10
    ) -> SchellenbergMessageReceived | None:
        """Mock pairing - simulates successful pairing."""
        self.pairing_message_received.clear()
        print(f"[MOCK] Simulating pairing for device {device_id}...")

        # Simulate a short wait
        await asyncio.sleep(2)

        # Create a mock pairing message
        print(f"[MOCK] Pairing simulation complete for device {device_id}")
        # In mock mode, we can't create a real pairing message without proper data
        # Return None to indicate mock mode
        return None

    async def exit(self):
        self.exit_event.set()
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
