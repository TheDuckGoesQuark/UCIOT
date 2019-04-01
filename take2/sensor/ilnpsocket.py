
from sensor.battery import Battery
from sensor.config import Configuration
from sensor.netinterface import NetworkInterface

NO_NEXT_HEADER_VALUE = 59


class ILNPSocket:
    def __init__(self, config: Configuration, battery: Battery):
        self.config: Configuration = config
        self.battery = battery
        self.net_interface: NetworkInterface = NetworkInterface(config)

    def close(self):
        self.net_interface.close()

    def send(self, data, dest_id):
        if self.battery.remaining() <= 0:
            self.close()
            raise IOError("Battery low: socket closing")
        elif self.is_closed():
            raise IOError("Socket is closed.")
        else:
            self.net_interface.send(data, dest_id)

    def is_closed(self) -> bool:
        return self.net_interface.closed
