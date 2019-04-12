import csv
import errno
import fcntl
import logging
import os
import time


class PacketEntry:
    """Record of a sent packet"""

    def __init__(self, my_id: int, sent_at_time, packet_type: str, forwarded: bool):
        """
        Record of sent or forwarded packet for analysis
        :param my_id id of node being recorded
        :param sent_at_time: epoch time packet was sent
        :param packet_type: type of packet (control or data)
        :param forwarded: was packet sent or forwarded by this node
        """
        self.node_id = my_id
        self.sent_at_time = sent_at_time
        self.packet_type = packet_type
        self.forwarded = forwarded


class Monitor:
    """Records sent packets and maintains global up status"""

    def __init__(self, node_id: int, save_file_loc: str):
        self.node_id = node_id
        self.entries = []
        self.save_file = save_file_loc
        self.running = True

    def record_sent_packet(self, is_control_message: bool, forwarded=True):
        if is_control_message:
            self.entries.append(PacketEntry(self.node_id, time.time(), "control", forwarded))
        else:
            self.entries.append(PacketEntry(self.node_id, time.time(), "data", forwarded))

    def save(self):
        with open(self.save_file, "a+") as csv_file:
            logging.debug("Attempting to gain log file lock")
            while True:
                # Loop to gain lock
                try:
                    fcntl.flock(csv_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    logging.debug("Lock obtained")
                    break
                except IOError as e:
                    if e.errno != errno.EAGAIN:
                        raise
                    else:
                        time.sleep(0.1)

            writer = csv.writer(csv_file, delimiter=',')
            if os.path.getsize(self.save_file) is 0:
                writer.writerow(["node_id", "sent_at_time", "packet_type", "forwarded"])

            for entry in self.entries:
                writer.writerow([entry.node_id, entry.sent_at_time, entry.packet_type, entry.forwarded])

            # Unlock
            logging.debug("Unlocking file")
            fcntl.flock(csv_file, fcntl.LOCK_UN)

