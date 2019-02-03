import argparse
from ilnpsocket.ilnpsocket import ILNPSocket

parser = argparse.ArgumentParser()
parser.add_argument("config", type=str, help="Path to config file.")
args = parser.parse_args()
config_file = args.config

sock = ILNPSocket(config_file)

sock.send(bytes("first packet for me", 'utf-8'), (0, 1))
sock.send(bytes("packet not for me but on my locator", 'utf-8'), (0, 2))
sock.send(bytes("packet not for me on different locator", "utf-8"), (2, 1))
sock.send(bytes("second packet for me but different", 'utf-8'), (1, 1))

print("Message received: {}".format(sock.receive()))
print("Message received: {}".format(sock.receive()))

