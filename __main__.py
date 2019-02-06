import argparse
from ilnpsocket.ilnpsocket import ILNPSocket

# init
parser = argparse.ArgumentParser()
parser.add_argument("config", type=str, help="Path to config file.")
parser.add_argument("section", type=str, help="Section in config file.")
args = parser.parse_args()
config_file = args.config
section = args.section

if __name__ == "__main__":
    sock = ILNPSocket(config_file, section)
    while True:
        print("Message for me received: {}".format(sock.receive()))
        sock.send(bytes("Hello you lovely little person you", "utf-8"), (1, 2))
else:
    sock = ILNPSocket(config_file, section)
