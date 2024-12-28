from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
import json
from asyncio import sleep
from random import randint

from typing import TypedDict
from general_functions import add_metadata


class SharedData(TypedDict):
    bins: list[str]
    trucks: list[str]
    self_ref: str


class PoleBehaviour(FSMBehaviour):
    def __init__(self, bins, trucks, self_ref):
        super().__init__()
        self.shared_data = SharedData(
            bins=bins,
            trucks=trucks,
            self_ref=self_ref
        )

    async def on_start(self):
        return await super().on_start()

    async def on_end(self):
        print(f'FSM finished at state {self.current_state}')
        await self.agent.stop()


class AwaitingDispatch(State):
    name = "AwaitingDispatch"

    def __init__(self, shared_data: SharedData):
        super().__init__()
        self.shared_data: SharedData = shared_data

    async def run(self):
        while True:  # endless listening for a bin to be full
            msg = await self.receive()
            if msg:
                body = json.loads(msg.body)
                if body["type"] == "Container Full":
                    ...

    async def send_confirmation(self, conversation_id, msg_id):
        msg = Message()
