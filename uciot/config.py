import ipaddress

LINK_LOCAL_MULTICAST = "FF02"
HEX_USER_ID = "4EA3"
UDP_IP = LINK_LOCAL_MULTICAST + "::" + HEX_USER_ID + ":1".decode('utf-8')

UDP_PORT = 8080
MESSAGE = "Hello World!"
MULTICAST_HOPS = 3

print("UDP target IP: {}".format(UDP_IP))
print("UDP target port: {}".format(UDP_PORT))
