import os

UDP_IP = "::1"  # ""ff02:" + str(os.getuid())
UDP_PORT = 5005
MESSAGE = "Hello World!"

print("UDP target IP: ", UDP_IP)
print("UDP target port: ", UDP_PORT)
