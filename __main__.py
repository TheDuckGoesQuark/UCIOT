import time

from ilnpsocket.ilnpsocket import ILNPSocket

sock = ILNPSocket("config.ini")
sock.send(bytes("first packet for me", 'utf-8'), (0, 1))
sock.send(bytes("packet not for me but on my locator", 'utf-8'), (0, 2))
sock.send(bytes("packet not for me on different locator", "utf-8"), (2, 1))
sock.send(bytes("second packet for me but different", 'utf-8'), (1, 1))

time.sleep(120)

print("Message received: {}".format(sock.receive()))
print("Message received: {}".format(sock.receive()))

