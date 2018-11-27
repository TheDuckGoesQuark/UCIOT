from queue import Queue

from uciot.underlay.listeningsocket import ListeningSocket
from uciot.underlay.sendingsocket import SendingSocket


class ILNPIO:
    """Abstracts UDP layer to leave only ILNP overlay"""

    def __init__(self, locators_to_ipv6, port_number):
        """
        Creates an instance able to send and receive ILNP packets.
        :param locators_to_ipv6: a map of locators and the corresponding ipv6 multicast address to be used
        :param port_number: port number to be used for UDP sockets
        """
        self.sender = SendingSocket()
        self.receivers = self.create_receivers(locators_to_ipv6, port_number)
        self.message_queue = Queue()

    def send(self, packet):
        return self.sender.sendTo(packet, self.receivers[packet.destination_locator])

    def receive(self, packet):


    def create_receivers(self, locators_to_ipv6, port_number):
        return {ListeningSocket(address, port_number, locator)
                for address, locator
                in locators_to_ipv6.items()}

