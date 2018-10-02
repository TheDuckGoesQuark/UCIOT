import threading
import time
import socket
import config


class ListeningThread(threading.Thread):
    def run(self):
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        print("Attempting to bind to socket")
        sock.bind(('', config.UDP_PORT))
        print("Successfully bound socket")

        # sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, config.MULTICAST_HOPS)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, True)

        print("Beginning listening")
        while True:
            data, address = sock.recvfrom(1024)
            print("received message '{}' from {} ".format(data.decode('utf-8'), address))


class SendingThread(threading.Thread):
    def run(self):
        print("Beginning sending")
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, True)
        for i in range(5):
            time.sleep(2)
            sock.sendto(config.MESSAGE.encode('utf-8'), (config.UDP_IP, config.UDP_PORT))

        sock.close()

        print("Finished sending")


if __name__ == '__main__':
    listening = ListeningThread()
    sending = SendingThread()
    listening.start()
    sending.start()
