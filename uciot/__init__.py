from uciot.ilnpsocket.ilnpsocket import ILNPSocket
from uciot.ilnpsocket.config import Config

if __name__ != "__main__":
    conf = Config("./config.ini")
    io = ILNPSocket(conf.locators_to_ipv6, conf.port)
    print("Try this command:")
    print("io.send(bytearray(b'345634563456345601828354285423458738754625helloworld872872592345013456'), '0')")
