"""
TODO

Multicast receiver and transmission threads (classes?)




"""
import threading
import time


class ListeningThread(threading.Thread):
    def run(self):
        print("The thing")


if __name__ == '__main__':
    for x in range(4):
        listener = ListeningThread(name="Thread-{}".format(x + 1))
        listener.start()
        time.sleep(.9)
