import os

LINK_LOCAL_MULTICAST = "ff02"
HEX_USER_ID = "4ea3"
UDP_IP = LINK_LOCAL_MULTICAST + ":" + HEX_USER_ID + "::1"
UDP_PORT = 5035
MESSAGE = "Hello World!"

print("UDP target IP: ", UDP_IP)
print("UDP target port: ", UDP_PORT)
