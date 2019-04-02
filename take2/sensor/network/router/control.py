import logging
import threading
import time
from functools import reduce
from math import sqrt
from multiprocessing import Queue
from queue import Empty
from typing import Tuple, List, Dict

from sensor.battery import Battery
from sensor.network.router.groupmessages import HelloGroup, HELLO_GROUP_ACK_TYPE, GroupMessage, HelloGroupAck, OKGroup, \
    HELLO_GROUP_TYPE, OK_GROUP_TYPE, OK_GROUP_ACK_TYPE, OKGroupAck, NEW_SENSOR_TYPE, NewSensor, NEW_SENSOR_ACK_TYPE, \
    NewSensorAck, KEEPALIVE_TYPE, CHANGE_CENTRAL_TYPE, ChangeCentral, CHANGE_CENTRAL_ACK_TYPE, ChangeCentralAck, \
    SENSOR_DISCONNECT_TYPE, SensorDisconnect, SENSOR_DISCONNECT_ACK_TYPE, SensorDisconnectAck, Link, KeepAlive
from sensor.network.router.ilnp import ILNPAddress, ILNPPacket
from sensor.network.router.forwardingtable import ForwardingTable, LinkGraph
from sensor.network.router.netinterface import NetworkInterface
from sensor.network.router.transportwrapper import build_control_wrapper

HELLO_GROUP_WAIT_SECS = 3

logger = logging.getLogger(__name__)

MAX_CONNECTIONS = 16
LOAD_PERCENTAGE = 50
MIN_ENERGY_TO_BE_NEIGHBOUR = 10
K_THREE_CONSTANT = 1000

KEEP_ALIVE_INTERVAL_SECS = 3
MAX_AGE_OF_LINK = KEEP_ALIVE_INTERVAL_SECS * 3


def max_average(loc_avg_a: Tuple[int, int], loc_avg_b: Tuple[int, int]) -> Tuple[int, int]:
    if loc_avg_a is None:
        return loc_avg_b

    if loc_avg_a[1] > loc_avg_b[1]:
        return loc_avg_a
    else:
        return loc_avg_b

def calc_neighbour_link_cost(neighbour_lambda, delay):
    return int(delay * K_THREE_CONSTANT / neighbour_lambda)


class RouterControlPlane(threading.Thread):
    def __init__(self, net_interface: NetworkInterface, control_packet_queue: Queue, my_address: ILNPAddress,
                 battery: Battery):
        super().__init__()
        self.central_node_id = my_address.id
        self.battery = battery
        self.my_address = my_address
        # Tracks neighbours and time since last keepalive
        self.internal_neighbours: Dict[int, int] = {}
        self.n_adjacent_nodes = 0
        self.net_interface = net_interface
        self.control_packet_queue = control_packet_queue
        self.running = False

        # Link table manages network knowledge
        self.link_graph = LinkGraph()
        # Forwarding table provides quick look-up for forwarding packets to internal and external nodes
        self.forwarding_table = ForwardingTable()

    def join(self, timeout=None) -> None:
        self.running = False
        super().join(timeout)

    def run(self) -> None:
        """Send keepalives and remove links that haven't sent one"""
        self.running = True
        while self.running:
            time.sleep(KEEP_ALIVE_INTERVAL_SECS)
            self.__send_keepalive()
            logger.info("Removing expired links")
            expired = [neighbour for neighbour, age in self.internal_neighbours if age > MAX_AGE_OF_LINK]
            self.internal_neighbours = [(neighbour, age + KEEP_ALIVE_INTERVAL_SECS)
                                        for neighbour, age in self.internal_neighbours
                                        if age <= MAX_AGE_OF_LINK]

            logger.info("links expired: {}".format(expired))
            self.__remove_expired_links(expired)

    def __send_keepalive(self):
        logger.info("Sending keepalive")
        keepalive = KeepAlive()
        t_wrap = build_control_wrapper(bytes(keepalive))
        packet = ILNPPacket(self.my_address, ILNPAddress(self.my_address.loc, 0), hop_limit=0,
                            payload_length=t_wrap.size_bytes(), payload=bytes(t_wrap))

        self.net_interface.broadcast(bytes(packet))

    def __remove_expired_links(self, expired: List[int]):
        sensor_disconnect = SensorDisconnect()
        t_wrap = build_control_wrapper(bytes(sensor_disconnect))

        for expired_node in expired:
            logger.info("Announcing that {} has expired".format(expired_node))
            self.link_graph.remove_vertex(expired_node)
            packet = ILNPPacket(ILNPAddress(self.my_address.loc, expired_node), ILNPAddress(self.my_address.loc, 0),
                                payload_length=t_wrap.size_bytes(), payload=bytes(t_wrap))
            self.net_interface.broadcast(bytes(packet))

        self.link_graph.update_forwarding_table(self.forwarding_table, self.my_address.id)

    def calc_my_lambda(self):
        return int((((MAX_CONNECTIONS - self.n_adjacent_nodes) * LOAD_PERCENTAGE) / MAX_CONNECTIONS) \
                   * sqrt((1 - ((self.battery.percentage() ** 2) / MIN_ENERGY_TO_BE_NEIGHBOUR))))

    def initialize_locator(self):
        """Broadcast node arrival and try to join/start group"""
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
            return
        else:
            logger.info("Fully parsing hellogroupack packets")
            for reply, delay in replies:
                reply.payload.body = HelloGroupAck.from_bytes(reply.payload.body)

        logger.info("Choosing best locator based on replies.")
        totals_and_count_for_locator = {}
        for reply, delay in replies:
            src_loc = reply.src.loc
            if src_loc not in totals_and_count_for_locator:
                totals_and_count_for_locator[src_loc] = (0, 0)

            current = totals_and_count_for_locator[src_loc]
            totals_and_count_for_locator[src_loc] = (current[0] + reply.payload.body.lambda_val, current[1] + 1)

        # Get best locator based on highest average lambda
        locator_to_average = \
            {locator: total / count for locator, (total, count) in totals_and_count_for_locator.items()}

        best_locator, best_average = \
            reduce(lambda current_max, next_val: max_average(current_max, next_val), locator_to_average.items())

        logger.debug("{} chosen as best locator to join".format(best_locator))
        self.n_adjacent_nodes = len({packet.src.id for packet, delay in replies})
        logger.debug("Identified {} neighbours".format(self.n_adjacent_nodes))
        self.my_address.loc = best_locator

        logger.info("Replying to hello group acks")
        for hello_group_ack, delay in replies:
            logger.info("Calculating cost to {}".format(hello_group_ack.src.id))
            self.forwarding_table.add_internal_entry(hello_group_ack.src.id, hello_group_ack.src.id)

            cost = calc_neighbour_link_cost(hello_group_ack.payload.body.lambda_val, delay)
            logger.info("Replying to {} with cost {}".format(str(hello_group_ack.src), cost))
            ok_group = OKGroup(cost)
            t_wrap = build_control_wrapper(bytes(ok_group))
            packet = ILNPPacket(self.my_address, hello_group_ack.src, hop_limit=0,
                                payload_length=t_wrap.size_bytes(), payload=bytes(t_wrap))

            self.net_interface.send(bytes(packet), hello_group_ack.src.id)

        logger.info("Waiting on ok group ack")
        group_acks = []
        logger.info("Collecting reply packets for the next {} seconds".format(HELLO_GROUP_WAIT_SECS))
        while time.time() < end:
            logger.info("Waiting for replies...")
            try:
                packet: ILNPPacket = self.control_packet_queue.get(block=True, timeout=HELLO_GROUP_WAIT_SECS)
            except Empty:
                continue

            logger.info("Got reply from group {}".format(packet.src.loc))
            group_acks.append(packet)

        logger.info("Removing any packets that aren't ok group acks from candidate join group")
        group_acks = [reply for reply in group_acks
                      if GroupMessage.parse_type(reply.payload.body) == OK_GROUP_ACK_TYPE
                      and reply.src.loc == best_locator]

        if len(group_acks) == 0:
            logger.info("No group acknowledgements. Starting again.")
            self.initialize_locator()
        else:
            logger.info("Fully parsing ok group ack packets")
            for reply in group_acks:
                reply.payload.body = OKGroupAck.from_bytes(reply.payload.body)
                self.__ok_group_ack_handler(reply)

            # Update forwarding table using new link state database
            self.link_graph.update_forwarding_table(self.forwarding_table, self.my_address.id)
            self.internal_neighbours = self.link_graph.get_neighbour_ids(self.my_address.id)

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
        """If node is joining my group, then begin informing the rest of the group and send it link state db"""
        if packet.src.loc != self.my_address.loc:
            logger.info("OK Group not for my group. Discarding")
            return

        logger.info("OK Group for my group. Informing other nodes of new link")
        link_entry = Link(self.my_address.id, packet.src.id, packet.payload.body.cost)
        self.forwarding_table.add_internal_entry(link_entry.node_b_id, link_entry.node_b_id)
        self.link_graph.add_edge(link_entry.node_a_id, link_entry.node_b_id, link_entry.cost)
        new_sensor = NewSensor(link_entry)
        t_wrap = build_control_wrapper(bytes(new_sensor))
        new_sensor_packet = ILNPPacket(self.my_address, ILNPAddress(self.my_address.loc, 0),
                                       payload_length=t_wrap.size_bytes(), payload=bytes(t_wrap))
        self.net_interface.broadcast(bytes(new_sensor_packet))

        logger.info("Acknowledging group join")
        link_entries = self.link_graph.to_link_list()
        ok_group_ack = OKGroupAck(len(link_entries), self.central_node_id, link_entries)
        t_wrap = build_control_wrapper(bytes(ok_group_ack))
        ok_group_ack_packet = ILNPPacket(self.my_address, ILNPAddress(self.my_address.loc, 0),
                                         payload_length=t_wrap.size_bytes(), payload=bytes(t_wrap))
        self.net_interface.send(bytes(ok_group_ack_packet), packet.src.id)

    def __ok_group_ack_handler(self, packet: ILNPPacket):
        """Update link state database based on reply"""
        if packet.src.loc != self.my_address.loc:
            logger.info("OK Group not for my group. Discarding")

        ok_group_ack: OKGroupAck = packet.payload.body
        self.central_node_id = ok_group_ack.central_node_id
        logger.info("Registering {} as central node".format(self.central_node_id))
        self.link_graph.add_edges(ok_group_ack.entry_list)

        logger.info("Initializing neighbour ages")
        self.internal_neighbours = {neighbour_id: 0 for neighbour_id in
                                    self.link_graph.get_neighbour_ids(self.my_address.id)}

    def __new_sensor_handler(self, packet: ILNPPacket):
        """Add new link to link state table, recompute paths"""
        if packet.src.loc != self.my_address.loc:
            logger.info("OK Group not for my group. Discarding")
            return

        new_sensor: NewSensor = packet.payload.body
        link = new_sensor.link_entry
        logger.info("Adding new link")
        self.link_graph.add_edge(link.node_a_id, link.node_b_id, link.cost)
        logger.info("Triggering forwarding table refresh")
        self.link_graph.update_forwarding_table(self.forwarding_table, self.my_address.id)
        self.__reverse_path_forward(packet)

    def __reverse_path_forward(self, packet: ILNPPacket):
        """Send packet onto nodes that are the same distance as me from origin + 1"""
        to_forward_to: List[int] = self.link_graph.get_neighbours_to_flood(self.my_address.id, packet.src.id)
        logger.info("Forwarding to {}".format(to_forward_to))
        packet.decrement_hop_limit()
        for next_hop in to_forward_to:
            self.net_interface.send(bytes(packet), next_hop)

    def __new_sensor_ack_handler(self, packet: ILNPPacket):
        """Nothing to do"""
        logging.info("Discarding new sensor ack.")

    def __keepalive_handler(self, packet: ILNPPacket):
        """Refresh age of neighbour link"""
        src_id = packet.src.id
        if src_id in self.internal_neighbours:
            self.internal_neighbours[src_id] = 0

    def __change_central_handler(self, packet: ILNPPacket):
        """Update central node in local knowledge"""
        if packet.src.loc != self.my_address.loc:
            logger.info("OK Group not for my group. Discarding")
            return
        # TODO
        pass

    def __change_central_ack_handler(self, packet: ILNPPacket):
        if packet.src.loc != self.my_address.loc:
            logger.info("OK Group not for my group. Discarding")
            return
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
            packet.payload.body = KeepAlive.from_bytes(packet.payload.body)
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
