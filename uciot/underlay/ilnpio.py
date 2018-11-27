from queue import Queue

from uciot.underlay.listeningsocket import ListeningSocket
from uciot.underlay.listeningthread import ListeningThread
from uciot.underlay.sendingsocket import SendingSocket


def create_receivers(locators_to_ipv6, port_number):
    """Creates a listening socket instance for each locator-ipv6 key value pair"""
    return [ListeningSocket(address, port_number, locator)
            for locator, address
            in locators_to_ipv6.items()]


class ILNPIO:
    """Abstracts UDP layer to leave only ILNP overlay"""

    def __init__(self, locators_to_ipv6, port_number):
        """
        Creates an io instance able to send and receive ILNP packets. A thread will be created for listening
        for incoming packets which will then populate the message queue, which can be polled using the receive method.
        :param locators_to_ipv6: a map of locators and the corresponding ipv6 multicast address to be used
        :param port_number: port number to be used for UDP sockets
        """
        self.sender = SendingSocket()
        self.locators_to_ipv6 = locators_to_ipv6
        receivers = create_receivers(locators_to_ipv6, port_number)
        self.message_queue = Queue()
        self.listening_thread = ListeningThread(receivers, self.message_queue)
        self.listening_thread.run()

    def send(self, packet_bytes, next_hop_locator):
        """
        Sends the given packet to the specified locator group.
        :param next_hop_locator: locator value packet should be sent to.
        :param packet_bytes: full ILNP packet to be sent as a bytearray
        :raises ValueError: if the next_hop_locator value is not a known locator to this node
        :return: number of bytes sent. Should match the size of the packet
        """
        if next_hop_locator not in self.locators_to_ipv6:
            raise ValueError("Next hop locator value is not known: {}".format(next_hop_locator))

        return self.sender.sendTo(packet_bytes, self.locators_to_ipv6[next_hop_locator])

    def receive(self, timeout=None):
        """Polls for packet. A timeout can be supplied"""
        return self.message_queue.get(block=True, timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self):
        """Closes sockets and joins thread upon exit"""
        self.listening_thread.stop()
        self.listening_thread.join()
        self.sender.close()
