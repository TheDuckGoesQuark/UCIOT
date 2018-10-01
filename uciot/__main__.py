import threading
import time
import socket
import config


class ListeningThread(threading.Thread):
    def run(self):
        print("Beginning listening")
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.bind((config.UDP_IP, config.UDP_PORT))

        while True:
            data, address = sock.recvfrom(1024)
            print("received message '{}' from {} ".format(data.decode('utf-8'), address))


class SendingThread(threading.Thread):
    def run(self):
        print("Beginning sending")
        for i in range(5):
            time.sleep(2)
            sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            sock.sendto(config.MESSAGE.encode('utf-8'), (config.UDP_IP, config.UDP_PORT))


if __name__ == '__main__':
    print("Sending messages from {}".format(config.UDP_IP))
    listening = ListeningThread()
    sending = SendingThread()
    listening.start()
    sending.start()
