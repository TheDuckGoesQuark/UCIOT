from uciot.ilnpsocket.ilnpsocket import ILNPSocket
from uciot.ilnpsocket.config import Config

if __name__ == "__main__":
    conf = Config("./config.ini")
    io = ILNPSocket(conf.locators_to_ipv6, conf.port)

    while True:
        packet = io.receive()
        if packet is not None:
            packet.print_packet()
