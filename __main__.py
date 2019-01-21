from ilnpsocket.ilnpsocket import ILNPSocket

sock = ILNPSocket("config.ini")
sock.send("hello world", (0, 1))
print(sock.receive())
