import math

from spade.agent import Agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour
from spade.message import Message
import json
from copy import deepcopy

from typing import TypedDict
from general_functions import add_metadata, SERVER_NAME


class SharedData(TypedDict):
    trucks: list[str]
    full_bin_id: str | None
    full_bin_pos: tuple[float, float] | None
    best_truck_id: str | None
    best_truck_pos: tuple[float, float] | None
    best_truck_dist: float | None
    self_ref: str


class PoleBehaviour(CyclicBehaviour):
    def __init__(self, trucks, self_ref):
        super().__init__()
        self.shared_data = SharedData(
            trucks=trucks,
            self_ref=self_ref,
            full_bin_id=None,
            full_bin_pos=None,
            best_truck_id=None,
            best_truck_pos=None,
            best_truck_dist=None
        )
    async def run(self):
        while True:  # endless listening for a bin full message
            msg = await self.receive()
            if msg:
                body = json.loads(msg.body)
                if body["type"] == "Container Full":
                    self.shared_data['full_bin_id'] = body['container']
                    self.shared_data['full_bin_pos'] = (body['position']['lon'], body['position']['lat'])
                    await self.send_confirmation(msg.metadata['conversation-id'], msg.metadata['reply-with'])
                    break
        handler = DispatchHandler(f"{msg.metadata['replay_with']}@{SERVER_NAME}", "1234", shared_data=deepcopy(self.shared_data))
        await handler.start(auto_register=True)
        self.shared_data['full_bin_id'] = None
        self.shared_data['full_bin_pos'] = None

    async def send_confirmation(self, conversation_id, msg_id):
        msg = Message(to=self.shared_data['full_bin_id'])
        msg.set_metadata("performative", "inform")
        msg.body = {
            'type': 'Acknowledge Container Full',
            'container': self.shared_data['full_bin_id'],
            'position': self.shared_data['full_bin_pos']
        }
        add_metadata(msg, conversation_id=conversation_id, in_replay_to=msg_id)
        await self.send(msg)

    async def on_start(self):
        return await super().on_start()

    async def on_end(self):
        await self.agent.stop()


class DispatchHandlerBehaviour(OneShotBehaviour):
    def __init__(self, shared_data):
        super().__init__()
        self.shared_data = shared_data

    async def on_start(self):
        return await super().on_start()

    async def on_end(self):
        await self.agent.stop()

    async def run(self):
        self.shared_data['best_truck_dist'] = 999.
        for truck_id in self.shared_data['trucks']:
            await self.send_position_request(truck_id=truck_id)
            msg = await self.receive(timeout=15)
            if msg:
                body = json.loads(msg.body)
                if body['type'] == 'Send Position':
                    await self.dispatch_truck(truck_id, (body['position']['lon'], body['position']['lat']))
        await self.send_dispatch()

    async def dispatch_truck(self, truck_id, truck_pos):
        current_dist = math.dist(self.shared_data['full_bin_pos'], truck_pos)
        if current_dist < self.shared_data['best_truck_dist']:
            self.shared_data['best_truck_dist'] = current_dist
            self.shared_data['best_truck_id'] = truck_id
            self.shared_data['best_truck_pos'] = truck_pos

    async def send_position_request(self, truck_id):
        msg = Message(to=truck_id)
        msg.set_metadata('performative', 'inform')
        msg.body = {
            'type': 'Request Position',
            'collector': truck_id
        }
        add_metadata(msg)
        await self.send(msg)

    async def send_dispatch(self):
        msg = Message(to=self.shared_data['best_truck_id'])
        msg.set_metadata('performative', 'inform')
        msg.body = {
            'type': 'Dispatch',
            'container': self.shared_data['full_bin_id'],
            'position': {
                'lon': self.shared_data['full_bin_pos'][0],
                'lat': self.shared_data['full_bin_pos'][1]
            }
        }
        add_metadata(msg)
        await self.send(msg)

class Pole(Agent):
    def __init__(self, *args, trucks):
        super().__init__(*args)
        self.trucks = trucks

    async def setup(self):
        print(f'Pole {self.jid} up and running')
        b = PoleBehaviour(self_ref=self.jid, trucks=self.trucks)
        self.add_behaviour(b)

class DispatchHandler(Agent):
    def __init__(self, *args, shared_data):
        super().__init__(*args)
        self.shared_data = shared_data

    async def setup(self):
        print(f'Dispatch {self.jid} up and running')
        b = DispatchHandlerBehaviour(shared_data=self.shared_data)
        self.add_behaviour(b)
