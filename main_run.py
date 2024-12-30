import yaml
from typing import TypedDict
from bin import Bin
from pole import Pole
from truck import Truck
from general_functions import SERVER_NAME
from random import randint
import spade

truck_num = 1
bin_num = 1


class Config(TypedDict):
    number_of_poles: int
    trucks_per_pole: int
    bins_per_pole: int

async def main():
    global truck_num
    global bin_num

    with open("config.yaml", "r") as f:
        config = Config(**yaml.safe_load(f))

    for num in range(config["number_of_poles"]):
        pole_name = f"pole_{num}@{SERVER_NAME}"
        pole_position = (randint(-100, 100), randint(-100, 100))
        truck_names = []
        for _ in range(config["trucks_per_pole"]):
            truck_position = [
                    pole_position[0] + randint(-10, 10),
                    pole_position[1] + randint(-10, 10)
            ]
            truck_name = f"truck_{truck_num}@{SERVER_NAME}"
            truck_names.append(truck_name)
            truck_num += 1
            truck_ = Truck(truck_name, "admin", connected_pole=pole_name, position=truck_position)
            await truck_.start(auto_register=True)
        pole = Pole(pole_name, "admin", trucks=truck_names)
        await pole.start(auto_register=True)
        for _ in range(config["bins_per_pole"]):
            bin_position = (
                pole_position[0] + randint(-10, 10),
                pole_position[1] + randint(-10, 10)
            )
            bin_name = f"bin_{bin_num}@{SERVER_NAME}"
            bin_num += 1
            print(bin_name)
            bin = Bin(bin_name, "admin", connected_pole=pole_name, position=bin_position)
            await bin.start(auto_register=True)

if __name__ == '__main__':
    spade.run(main())
