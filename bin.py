from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
import json
from asyncio import sleep
from random import randint

from typing import TypedDict
from general_functions import add_metadata


class SharedData(TypedDict):
    fullness: int
    max_capacity: int
    connected_pole: str
    self_ref: str
    position: tuple[int, int]


class BinBehaviour(FSMBehaviour):
    def __init__(self, connected_pole, self_ref, position):
        super().__init__()
        self.shared_data = SharedData(
            fullness=0,
            max_capacity=20,
            connected_pole=connected_pole,
            self_ref=self_ref,
            position=position
        )

    async def on_start(self):
        pass

    async def on_end(self):
        print(f"FSM finished at state {self.current_state}")
        await self.agent.stop()


class FillingBehv(State):
    name = "Filling"

    def __init__(self, shared_data: SharedData):
        super().__init__()
        self.shared_data: SharedData = shared_data

    async def run(self):
        while True:
            if randint(0, 10) == 0:  # 10% to fill in each tick
                self.shared_data["fullness"] += 1
            await sleep(1)
            if self.shared_data["fullness"] == self.shared_data["max_capacity"]:
                break
        msg = Message(to=self.shared_data["connected_pole"])
        msg.set_metadata("performative", "inform")
        msg.body = {
            "type": "Container Full",
            "container": self.shared_data["self_ref"],
            "position": {
                "lon": self.shared_data["position"][0],
                "lat": self.shared_data["position"][0]
            }
        }
        add_metadata(msg)

        await self.send(msg)
        self.set_next_state(AwaitingPickup.name)


class AwaitingPickup(State):
    name = "AwaitingPickup"

    def __init__(self, shared_data: SharedData):
        super().__init__()
        self.shared_data: SharedData = shared_data

    async def run(self):
        while True:  # endless listening for pickup
            msg = await self.receive(timeout=10)
            if msg:
                body = json.loads(msg.body)
                if body["type"] != "Empty Confirmation":
                    continue
                if body["container"] == self.shared_data["self_ref"]:
                    break

        self.shared_data["fullness"] = 0
        self.set_next_state(FillingBehv.name)


class Bin(Agent):
    def __init__(self, *args, connected_pole, position):
        super().__init__(*args)
        self.connected_pole = connected_pole
        self.position = position

    async def setup(self):
        print(f'Bin {self.jid} up and running')
        b = BinBehaviour(self.connected_pole, self.jid, self.position)
        b.add_state(FillingBehv.name, state=FillingBehv(b.shared_data), initial=True)
        b.add_state(AwaitingPickup.name, state=AwaitingPickup(b.shared_data))
        b.add_transition(source=FillingBehv.name, dest=AwaitingPickup.name)
        b.add_transition(source=AwaitingPickup.name, dest=FillingBehv.name)
        self.add_behaviour(b)
