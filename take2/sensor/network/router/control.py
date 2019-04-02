import logging
import time
from functools import reduce
from math import sqrt
from multiprocessing import Queue
from queue import Empty
from typing import Tuple, List

from sensor.battery import Battery
from sensor.network.router.groupmessages import HelloGroup, HELLO_GROUP_ACK_TYPE, GroupMessage, HelloGroupAck, OKGroup, \
    HELLO_GROUP_TYPE, OK_GROUP_TYPE, OK_GROUP_ACK_TYPE, OKGroupAck, NEW_SENSOR_TYPE, NewSensor, NEW_SENSOR_ACK_TYPE, \
    NewSensorAck, KEEPALIVE_TYPE, CHANGE_CENTRAL_TYPE, ChangeCentral, CHANGE_CENTRAL_ACK_TYPE, ChangeCentralAck, \
    SENSOR_DISCONNECT_TYPE, SensorDisconnect, SENSOR_DISCONNECT_ACK_TYPE, SensorDisconnectAck
from sensor.network.router.ilnp import ILNPAddress, ILNPPacket
from sensor.network.router.linktable import LinkTable
from sensor.network.router.netinterface import NetworkInterface
from sensor.network.router.transportwrapper import build_control_wrapper

HELLO_GROUP_WAIT_SECS = 3

logger = logging.getLogger(__name__)

MAX_CONNECTIONS = 16
LOAD_PERCENTAGE = 50
MIN_ENERGY_TO_BE_NEIGHBOUR = 10
K_THREE_CONSTANT = 1000


def max_average(loc_avg_a: Tuple[int, int], loc_avg_b: Tuple[int, int]) -> Tuple[int, int]:
    if loc_avg_a[1] > loc_avg_b[1]:
        return loc_avg_a
    else:
        return loc_avg_b


def calc_neighbour_link_cost(neighbour_lambda, delay):
    return int(delay * K_THREE_CONSTANT / neighbour_lambda)


class RouterControlPlane:
    def __init__(self, net_interface: NetworkInterface, control_packet_queue: Queue, my_address: ILNPAddress,
                 battery: Battery):
        self.battery = battery
        self.my_address = my_address
        self.n_neighbours = 0
        self.net_interface = net_interface
        self.control_packet_queue = control_packet_queue
        self.link_table = LinkTable()

    def calc_my_lambda(self):
        return (((MAX_CONNECTIONS - self.n_neighbours) * LOAD_PERCENTAGE) / MAX_CONNECTIONS) \
               * sqrt((1 - ((self.battery.percentage() ** 2) / MIN_ENERGY_TO_BE_NEIGHBOUR)))

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

        logger.info("Broadcasting hello group message")
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

        logger.debug("{} chosen as best locator to join".format(best_locator))
        self.n_neighbours = len(replies)
        logger.debug("Identified {} neighbours".format(self.n_neighbours))
        self.my_address.loc = best_locator
        self.__reply_to_hello_group_acks(replies)

    def __reply_to_hello_group_acks(self, hello_groups: List[Tuple[ILNPPacket, float]]):
        logging.info("Replying to hello group acks")
        for reply, delay in hello_groups:
            ok_group = OKGroup(calc_neighbour_link_cost(reply.payload.body.lambda_val, delay))
            self.link_table.add_entry(reply.src.id, reply.src.id, ok_group.cost)
            logging.info("Replying to {} with cost {}".format(str(reply.src), ok_group.cost))
            t_wrap = build_control_wrapper(bytes(ok_group))
            packet = ILNPPacket(self.my_address, reply.src, hop_limit=0,
                                payload_length=t_wrap.size_bytes(), payload=bytes(t_wrap))
            self.net_interface.send(bytes(packet), reply.src.id)

    def __hello_group_handler(self, packet: ILNPPacket):
        """On receiving a hello group message, reply with my lambda value"""
        hg_ack = HelloGroupAck(self.calc_my_lambda())
        t_wrap = build_control_wrapper(bytes(hg_ack))
        reply_packet = ILNPPacket(self.my_address, packet.src, hop_limit=0,
                                  payload_length=t_wrap.size_bytes(), payload=bytes(t_wrap))

        self.net_interface.send(bytes(reply_packet), packet.src.id)

    def __hello_group_ack_handler(self, packet: ILNPPacket):
        """Hello group ack only useful during group joining/forming phase"""
        logging.info("Discarding hello group ack.")

    def __ok_group_handler(self, packet: ILNPPacket):
        """If node is joining my group, then begin informing the rest of the group"""
        # TODO
        pass

    def __ok_group_ack_handler(self, packet: ILNPPacket):
        """Update link state database based on reply"""
        # TODO
        pass

    def __new_sensor_handler(self, packet: ILNPPacket):
        """Add new link to link state table, recompute paths"""
        # TODO
        pass

    def __new_sensor_ack_handler(self, packet: ILNPPacket):
        """Nothing to do"""
        logging.info("Discarding new sensor ack.")

    def __keepalive_handler(self, packet: ILNPPacket):
        """Refresh age of neighbour link"""
        # TODO
        pass

    def __change_central_handler(self, packet: ILNPPacket):
        """Update central node in local knowledge"""
        # TODO
        pass

    def __change_central_ack_handler(self, packet: ILNPPacket):
        """Nothing to do"""
        logging.info("Discarding new central ack.")

    def __sensor_disconnect_handler(self, packet: ILNPPacket):
        """remove links from link state table to the failing node, recompute paths"""
        # TODO
        pass

    def __sensor_disconnect_ack_handler(self, packet: ILNPPacket):
        """Nothing to do"""
        logging.info("Discarding new sensor disconnect ack.")

    def handle_packet(self, packet: ILNPPacket):
        type_val = GroupMessage.parse_type(packet.payload.body)
        if type_val is HELLO_GROUP_TYPE:
            logger.info("hello group messaged received")
            packet.payload.body = HelloGroup.from_bytes(packet.payload.body)
            self.__hello_group_handler(packet)
        elif type_val is HELLO_GROUP_ACK_TYPE:
            logger.info("hello group ack messaged received")
            packet.payload.body = HelloGroupAck.from_bytes(packet.payload.body)
        elif type_val is OK_GROUP_TYPE:
            logger.info("ok group messaged received")
            packet.payload.body = OKGroup.from_bytes(packet.payload.body)
        elif type_val is OK_GROUP_ACK_TYPE:
            logger.info("ok group ack messaged received")
            packet.payload.body = OKGroupAck.from_bytes(packet.payload.body)
        elif type_val is NEW_SENSOR_TYPE:
            logger.info("new sensor messaged received")
            packet.payload.body = NewSensor.from_bytes(packet.payload.body)
        elif type_val is NEW_SENSOR_ACK_TYPE:
            logger.info("new sensor ack messaged received")
            packet.payload.body = NewSensorAck.from_bytes(packet.payload.body)
        elif type_val is KEEPALIVE_TYPE:
            logger.info("keepalive messaged received")
            packet.payload.body = KEEPALIVE_TYPE.from_bytes(packet.payload.body)
        elif type_val is CHANGE_CENTRAL_TYPE:
            logger.info("change central messaged received")
            packet.payload.body = ChangeCentral.from_bytes(packet.payload.body)
        elif type_val is CHANGE_CENTRAL_ACK_TYPE:
            logger.info("change central ack messaged received")
            packet.payload.body = ChangeCentralAck.from_bytes(packet.payload.body)
        elif type_val is SENSOR_DISCONNECT_TYPE:
            logger.info("sensor disconnect messaged received")
            packet.payload.body = SensorDisconnect.from_bytes(packet.payload.body)
        elif type_val is SENSOR_DISCONNECT_ACK_TYPE:
            logger.info("sensor disconnect ack messaged received")
            packet.payload.body = SensorDisconnectAck.from_bytes(packet.payload.body)
