from time import sleep

from config import Config
from listeningthread import ListeningThread
from messagequeue import message_queue
from routingthread import RoutingThread


def simulateTraffic(sleep_in_secs, payload):
    while True:
        message_queue.put('"src_address": 0, "dest_address":0, "payload":"hello world", "hop_limit":3}')
        sleep(sleep_in_secs)


def create_listening_threads(addresses, port):
    return [ListeningThread(port, address) for address in addresses]


def begin_listening_threads(threads):
    for thread in threads:
        thread.start()


def initialize_listening_threads(addresses, port):
    listening_threads = create_listening_threads(addresses, port)
    begin_listening_threads(listening_threads)


def initialize_routing_thread(port, address):
    routing = RoutingThread(port, address)
    routing.start()


if __name__ == '__main__':
    config = Config()
    initialize_listening_threads(config.ipv6_multicast_addresses, config.port)
    initialize_routing_thread(config.port, config.ipv6_multicast_addresses[0])
    simulateTraffic(config.sleep, config.message)
