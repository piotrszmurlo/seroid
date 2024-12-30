from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
import json
from asyncio import sleep
import time
from random import randint

from typing import TypedDict
from general_functions import add_metadata


class SharedData(TypedDict):
    fullness: int
    max_capacity: int
    connected_pole: str
    connected_dispatcher: str
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
            max_capacity=3,
            connected_pole=connected_pole,
            connected_dispatcher=None,
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
                if body["type"] == "Request Position" and body["collector"] == str(self.shared_data["self_ref"]):
                    self.shared_data['connected_dispatcher'] = str(msg.sender)
                    print(f'{self.shared_data["self_ref"]} received Request Position message from {self.shared_data["connected_dispatcher"]}')
                    await self.send_position(msg.metadata["conversation_id"], msg.metadata["reply_with"])
                
                elif body["type"] == "Dispatch":
                    print(f"{self.shared_data["self_ref"]}: Received dispatch request from {self.shared_data["connected_dispatcher"]}")
                    # await self.send_confirmation(msg.metadata["conversation_id"], msg.metadata["reply_with"])
                    self.shared_data["current_container"] = body["container"]
                    self.shared_data["current_container_pos"] = (body["position"]["lon"], body["position"]["lat"])
                    print(f'{self.shared_data["self_ref"]}: heading to {self.shared_data["current_container"]}, pos: ({body["position"]["lon"]}, {body["position"]["lat"]})')
                    break
            self.wander()
        self.set_next_state(EmptyingBin.name)

    async def send_position(self, conversation_id, msg_id):
        msg = Message(to=self.shared_data["connected_dispatcher"])
        msg.set_metadata("performative", "inform")
        msg.body = json.dumps({
            "type": "Send Position",
            "position": {
                "lon": self.shared_data["position"][0],
                "lat": self.shared_data["position"][0]
            }
        })
        add_metadata(msg, conversation_id=conversation_id, in_reply_to=msg_id)
        await self.send(msg)
        print(f'{self.shared_data["self_ref"]}: sending position to {self.shared_data["connected_dispatcher"]}')


    def wander(self):
        print(f"{self.shared_data["self_ref"]}: wandering...")
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
    name = "EmptyingBin"

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
        msg = Message(to=self.shared_data["current_container"])
        msg.set_metadata("performative", "inform")
        msg.body = json.dumps({
            "type": "Empty Confirmation",
            "container": str(self.shared_data["current_container"])
        })
        add_metadata(msg)
        await self.send(msg)
        self.shared_data["fullness"] += 1
        print(f'{self.shared_data["self_ref"]}: collected load from {str(self.shared_data["current_container"])}\ncurrent fullness: {self.shared_data["fullness"]}/{self.shared_data["max_capacity"]}, sending empty confirmation')
        self.shared_data["current_container"] = None
        self.shared_data["current_container_pos"] = None
        if self.shared_data["fullness"] == self.shared_data["max_capacity"]:
            self.set_next_state(EmptyingTruck.name)
        else:
            self.set_next_state(AwaitingDispatch.name)


class EmptyingTruck(State):
    name = "EmptyingTruck"

    def __init__(self, shared_data: SharedData):
        super().__init__()
        self.shared_data: SharedData = shared_data

    async def run(self):
        EMPTYING_SLEEP = 20
        print(f'{self.shared_data["self_ref"]}: Emptying myself (brb {EMPTYING_SLEEP} seconds)')
        await sleep(EMPTYING_SLEEP)
        self.shared_data['fullness'] = 0
        self.set_next_state(AwaitingDispatch.name)


class Truck(Agent):
    def __init__(self, *args, connected_pole, position):
        super().__init__(*args)
        self.connected_pole = connected_pole
        self.position = position

    async def setup(self):
        print(f'Truck {self.jid} up and running')
        b = TruckBehaviour(self.connected_pole, self.jid, self.position)
        b.add_state(AwaitingDispatch.name, state=AwaitingDispatch(b.shared_data), initial=True)
        b.add_state(EmptyingBin.name, state=EmptyingBin(b.shared_data))
        b.add_state(EmptyingTruck.name, state=EmptyingTruck(b.shared_data))
        b.add_transition(source=AwaitingDispatch.name, dest=EmptyingBin.name)
        b.add_transition(source=EmptyingBin.name, dest=EmptyingTruck.name)
        b.add_transition(source=EmptyingBin.name, dest=AwaitingDispatch.name)
        b.add_transition(source=EmptyingTruck.name, dest=AwaitingDispatch.name)
        b.add_transition(source=Truck.name, dest=AwaitingDispatch.name)
        self.add_behaviour(b)
