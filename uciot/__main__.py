"""
TODO

Multicast receiver and transmission threads (classes?)

"""
import threading
import time
import socket
import os
import config


class ListeningThread(threading.Thread):
    def run(self):
        print("Beginning listening")
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.bind((config.UDP_IP, config.UDP_PORT))

        while True:
            data = sock.recv(1024)
            print("received message: ", data.decode('utf-8'))


class SendingThread(threading.Thread):
    def run(self):
        print("Beginning sending")
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.sendto(config.MESSAGE.encode('utf-8'), (config.UDP_IP, config.UDP_PORT))


if __name__ == '__main__':
    listening = ListeningThread()
    sending = SendingThread()
    listening.start()
    sending.start()
