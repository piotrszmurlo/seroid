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
    position: list[int, int]
    center_position: tuple[int, int]
    current_container: str | None
    current_container_pos: tuple[int, int] | None


class TruckBehaviour(FSMBehaviour):
    def __init__(self, connected_pole, self_ref, position):
        super().__init__()
        self.shared_data = SharedData(
            fullness=0,
            max_capacity=20,
            connected_pole=connected_pole,
            self_ref=self_ref,
            position=position,
            center_position=position,
            current_container=None,
            current_container_pos=None
        )

    async def on_start(self):
        pass

    async def on_end(self):
        print(f"FSM finished at state {self.current_state}")
        await self.agent.stop()


class AwaitingDispatch(State):
    name = "AwaitingDispatch"

    def __init__(self, shared_data: SharedData):
        super().__init__()
        self.shared_data: SharedData = shared_data

    async def run(self):
        while True:  # endless listening for pickup
            msg = await self.receive(timeout=10)
            if msg:
                body = json.loads(msg.body)
                if body["type"] != "Request Position" and body["collector"] == self.shared_data["self_ref"]:
                    await self.send_position(msg.metadata["conversation-id"], msg.metadata["reply-with"])

                if body["type"] != "Dispatch":
                    await self.send_confirmation(msg.metadata["conversation-id"], msg.metadata["reply-with"])
                    self.shared_data["current_container"] = body["container"]
                    self.shared_data["current_container_pos"] = (body["position"]["lon"], body["position"]["lat"])
                    break
            self.wander()
        self.set_next_state(EmptyingBin.name)

    async def send_position(self, conversation_id, msg_id):
        msg = Message(to=self.shared_data["connected_pole"])
        msg.set_metadata("performative", "inform")
        msg.body = {
            "type": "Send Position",
            "position": {
                "lon": self.shared_data["position"][0],
                "lat": self.shared_data["position"][0]
            }
        }
        add_metadata(msg, conversation_id=conversation_id, in_replay_to=msg_id)
        await self.send(msg)

    async def send_confirmation(self, conversation_id, msg_id):
        msg = Message(to=self.shared_data["connected_pole"])
        msg.set_metadata("performative", "inform")
        msg.body = {
            "type": "Accept Dispatch",
            "value": True
        }
        add_metadata(msg, conversation_id=conversation_id, in_replay_to=msg_id)
        await self.send(msg)

    def wander(self):
        for _ in range(10):
            self.step()

    def step(self):
        direction = randint(0, 1)
        side = randint(-100, 100)
        pos = self.shared_data["position"][direction]
        center = self.shared_data["center_position"][direction]
        offset = pos - center
        if offset >= side:
            self.shared_data["position"][direction] += 1
        else:
            self.shared_data["position"][direction] -= 1


class EmptyingBin(State):
    name = "Emptying"

    def __init__(self, shared_data: SharedData):
        super().__init__()
        self.shared_data: SharedData = shared_data

    async def run(self):
        length = abs(self.shared_data["position"][0] - self.shared_data["current_container_pos"][0])
        length += abs(self.shared_data["position"][1] - self.shared_data["current_container_pos"][1])
        await sleep(length)
        self.shared_data["position"] = list(self.shared_data["current_container_pos"])
        await self.empty()

    async def empty(self):
        msg = Message(to=self.shared_data["connected_pole"])
        msg.set_metadata("performative", "inform")
        msg.body = {
            "type": "Empty Confirmation",
            "container": self.shared_data["current_container"]
        }
        add_metadata(msg)
        await self.send(msg)
        self.shared_data["fullness"] += 1
        self.shared_data["current_container"] = None
        self.shared_data["current_container_pos"] = None

        if self.shared_data["fullness"] == self.shared_data["max_capacity"]:
            self.set_next_state(Emptying.name)
        else:
            self.set_next_state(AwaitingDispatch.name)


class Emptying(State):
    name = "EmptyingTruck"

    async def run(self):
        await sleep(60)
        self.set_next_state(AwaitingDispatch.name)


class Bin(Agent):
    def __init__(self, *args, connected_pole, position):
        super().__init__(*args)
        self.connected_pole = connected_pole
        self.position = position

    async def setup(self):
        print("SenderAgent started")
        b = TruckBehaviour(self.connected_pole, self.jid, self.position)
        b.add_state(AwaitingDispatch.name, state=AwaitingDispatch(b.shared_data), initial=True)
        b.add_state(EmptyingBin.name, state=EmptyingBin(b.shared_data))
        b.add_transition(source=AwaitingDispatch.name, dest=EmptyingBin.name)
        b.add_transition(source=EmptyingBin.name, dest=Emptying.name)
        b.add_transition(source=EmptyingBin.name, dest=AwaitingDispatch.name)
        b.add_transition(source=Emptying.name, dest=AwaitingDispatch.name)
        self.add_behaviour(b)
