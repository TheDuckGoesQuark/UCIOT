import struct
import threading
import time
import socket
import config


class ListeningThread(threading.Thread):
    def run(self):
        # Initialise socket for IPv6 datagrams
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

        # Allows address to be reused
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Binds to any interface on the given port
        sock.bind(('', config.UDP_PORT))

        # Allow messages from this socket to loop back
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, True)

        # Construct message for joining multicast group
        mreq = struct.pack("16s15s", socket.inet_pton(socket.AF_INET6, config.UDP_IP), chr(0) * 16)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)

        print("Beginning listening")
        while True:
            # Create a buffer of size 1024 to receive messages
            data, address = sock.recvfrom(1024)
            print("received message '{}' from {} ".format(data.decode('utf-8'), address))


class SendingThread(threading.Thread):
    def run(self):
        print("Beginning sending")
        # Configure socket for sending IPv6 Datagrams
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, True)
        for i in range(5):
            time.sleep(2)
            # Send message to multicast group
            sock.sendto(config.MESSAGE, (config.UDP_IP, config.UDP_PORT))

        sock.close()

        print("Finished sending")


if __name__ == '__main__':
    listening = ListeningThread()
    sending = SendingThread()
    listening.start()
    sending.start()
