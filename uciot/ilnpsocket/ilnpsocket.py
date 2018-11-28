from queue import Queue

from uciot import Config
from uciot.ilnpsocket.underlay.listeningsocket import ListeningSocket
from uciot.ilnpsocket.underlay.listeningthread import ListeningThread
from uciot.ilnpsocket.underlay.sendingsocket import SendingSocket


def create_receivers(locators_to_ipv6, port_number):
    """Creates a listening socket instance for each locator-ipv6 key value pair"""
    return [ListeningSocket(address, port_number, locator)
            for locator, address
            in locators_to_ipv6.items()]


class ILNPSocket:
    """Abstracts UDP layer to leave only ILNP overlay"""

    def __init__(self, config_file):
        """
        Creates an io instance able to send and receive ILNP packets. A thread will be created for listening
        for incoming packets which will then populate the message queue, which can be polled using the receive method.
        """
        # Parse config file
        conf = Config(config_file)
        port_number = conf.port
        locators_to_ipv6 = conf.locators_to_ipv6

        # Create sending socket
        self.__locators_to_ipv6 = locators_to_ipv6
        self.__sender = SendingSocket(port_number)

        # Configures listening thread
        receivers = create_receivers(locators_to_ipv6, port_number)
        self.__message_queue = Queue()
        self.__listening_thread = ListeningThread(receivers, self.__message_queue)
        # Child threads die with parent
        self.__listening_thread.daemon = True
        self.__listening_thread.start()
        print("ILNP IO Initialised")

    def send(self, packet_bytes, next_hop_locator):
        """
        Sends the given packet to the specified locator group.
        :param next_hop_locator: locator value packet should be sent to.
        :param packet_bytes: full ILNP packet to be sent as a bytearray
        :raises ValueError: if the next_hop_locator value is not a known locator to this node
        :return: number of bytes sent. Should match the size of the packet
        """
        if next_hop_locator not in self.__locators_to_ipv6:
            raise ValueError("Next hop locator value is not known: {}".format(next_hop_locator))

        return self.__sender.sendTo(packet_bytes, self.__locators_to_ipv6[next_hop_locator])

    def receive(self, timeout=None):
        """Polls for packet. A timeout can be supplied"""
        try:
            packet = self.__message_queue.get(block=True, timeout=timeout)
        except KeyboardInterrupt:
            return

        if packet is None:
            return

        self.__message_queue.task_done()
        return packet

    def __enter__(self):
        return self

    def __exit__(self):
        """Closes sockets and joins thread upon exit"""
        self.__listening_thread.stop()
        self.__listening_thread.join()
        self.__sender.close()
