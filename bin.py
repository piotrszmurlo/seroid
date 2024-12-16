from spade.agent import Agent
from spade.behaviour import OneShotBehaviour, FSMBehaviour, State
from spade.message import Message
from spade.template import Template
import spade
import asyncio
from asyncio import sleep
from random import randint

from typing import OrderedDict, TypedDict

class SharedData(TypedDict):
    fullness: int
    max_capacity: int
    connected_pole: str


class BinBehaviour(FSMBehaviour):
    def __init__(self, connected_pole):
        super().__init__()
        self.shared_data = SharedData(fullness=0, max_capacity=20, connected_pole=connected_pole)

    async def on_start(self):
        pass

    async def on_end(self):
        print(f"FSM finished at state {self.current_state}")
        await self.agent.stop()



class FillingBehv(State):
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
        msg.body = "filled"  # nie pamiętam pelnej struktury

        await self.send(msg)
        self.set_next_state("AwaitingPickup")

class AwaitingPickup(State):
    def __init__(self, shared_data: SharedData):
        super().__init__()
        self.shared_data: SharedData = shared_data
    async def run(self):
        pass

class Bin(Agent):
    def __init__(self, *args, connected_pole):
        super().__init__(*args)
        self.connected_pole = connected_pole

    async def setup(self):
        print("SenderAgent started")
        b = BinBehaviour(self.connected_pole)
        b.add_state("Filling", state=FillingBehv(b.shared_data), initial=True)
        b.add_state("AwaitingPickup", state=AwaitingPickup(b.shared_data))
        b.add_transition(source="Filling", dest="AwaitingPickup")
        self.add_behaviour(b)
