from uciot.ilnpio import ILNPIO
from uciot.config import Config

conf = Config("./uciot/config.ini")
io = ILNPIO(conf.locators_to_ipv6, conf.port)

if __name__ == "__main__":
    while True:
        io.receive().print_packet()
