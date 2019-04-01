import logging
import time
from functools import reduce
from multiprocessing import Queue
from queue import Empty
from typing import Dict, Tuple, List, Iterable

from sensor.network.groupmessages import HelloGroup, HELLO_GROUP_ACK_TYPE, GroupMessage, HelloGroupAck
from sensor.network.ilnp import ILNPAddress, ILNPPacket
from sensor.network.netinterface import NetworkInterface
from sensor.network.transportwrapper import build_control_wrapper

HELLO_GROUP_WAIT_SECS = 3

logger = logging.getLogger(__name__)


def max_average(loc_avg_a: Tuple[int, int], loc_avg_b: Tuple[int, int]) -> Tuple[int, int]:
    if loc_avg_a[1] > loc_avg_b[1]:
        return loc_avg_a
    else:
        return loc_avg_b


class RouterControlPlane:
    def __init__(self, net_interface: NetworkInterface, control_packet_queue: Queue, my_address: ILNPAddress):
        self.my_address = my_address
        self.net_interface = net_interface
        self.control_packet_queue = control_packet_queue

    def initialize_locator(self):
        """
        Broadcast node arrival and try to join/start group
        :returns this nodes locator
        """
        logger.info("Constructing hello group message")
        hello_group_msg = HelloGroup()
        t_wrap = build_control_wrapper(bytes(hello_group_msg))
        # One hop so only neighbours process, no specified destination
        packet = ILNPPacket(self.my_address, ILNPAddress(0, 0), hop_limit=0,
                            payload=t_wrap, payload_length=t_wrap.size_bytes())

        # Collect packets and delay between send and receive
        replies: List[Tuple[ILNPPacket, float]] = []

        logging.info("Broadcasting hello group message")
        self.net_interface.broadcast(bytes(packet))
        start = time.time()
        end = start + HELLO_GROUP_WAIT_SECS

        logger.info("Collecting reply packets for the next {} seconds".format(HELLO_GROUP_WAIT_SECS))
        while time.time() < end:
            logger.info("Waiting for replies...")
            try:
                packet: ILNPPacket = self.control_packet_queue.get(block=True, timeout=HELLO_GROUP_WAIT_SECS)
            except Empty:
                continue

            delay = time.time() - start
            logger.info("Got reply from group {}".format(packet.src.loc))
            replies.append((packet, delay))

        logger.info("Removing any packets that aren't join group acks")
        replies = [(reply, delay) for reply, delay in replies
                   if GroupMessage.parse_type(reply.payload.body) == HELLO_GROUP_ACK_TYPE]

        if len(replies) == 0:
            logger.info("No replies. Using configuration locator {}.".format(self.my_address.loc))
        else:
            logger.info("Fully parsing hellogroupack packets")
            for reply, delay in replies:
                reply.payload.body = HelloGroupAck.from_bytes(reply.payload.body)

            self.__handle_hello_group_acks(replies)

    def __handle_hello_group_acks(self, replies: List[Tuple[ILNPPacket, float]]):
        logger.info("Choosing best locator based on replies.")
        totals_and_count_for_locator = {}
        for reply, delay in replies:
            src_loc = reply.src.loc
            if src_loc not in totals_and_count_for_locator:
                totals_and_count_for_locator[src_loc] = (0, 0)

            totals_and_count_for_locator[src_loc][0] += reply.payload.body.lambda_val
            totals_and_count_for_locator[src_loc][1] += 1

        # Get best locator based on highest average lambda
        locator_to_average = \
            {locator: total / count for locator, (total, count) in totals_and_count_for_locator.items()}

        best_locator, best_average_lambda = \
            reduce(lambda current_max, next_val: max_average(current_max, next_val), locator_to_average)

        logging.debug("{} chosen as best locator to join".format(best_locator))

        # Filter replies from other groups
        replies = [(reply, delay) for reply, delay in replies if reply.src.loc == best_locator]



    def handle_packet(self, param):
        pass
