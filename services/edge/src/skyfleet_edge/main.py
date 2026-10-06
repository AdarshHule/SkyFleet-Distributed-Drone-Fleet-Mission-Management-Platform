import time

from skyfleet_edge.drone import VirtualDrone


def main() -> None:
    drone = VirtualDrone("SF-PN-001", latitude=18.5204, longitude=73.8567)
    drone.fly_to(18.5300, 73.8567)
    while True:
        drone.step(1.0)
        print(drone.to_telemetry().model_dump_json())
        time.sleep(1.0)


if __name__ == "__main__":
    main()
