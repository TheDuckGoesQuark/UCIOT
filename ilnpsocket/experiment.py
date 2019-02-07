import csv
import errno
import fcntl
import logging
import time


class Monitor:
    def __init__(self, number_of_sends, node_id, save_file_loc):
        self.number_of_sends = number_of_sends
        self.data_sent = 0
        self.control_packets_sent = 0
        self.node_id = node_id
        self.save_file = save_file_loc

    def record_sent_packet(self, packet):
        if packet.is_control_message():
            self.control_packets_sent = self.control_packets_sent + 1
        else:
            self.data_sent = self.data_sent + 1

        self.number_of_sends = self.number_of_sends + 1

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
            # TODO

            # Unlock
            logging.debug("Unlocking file")
            fcntl.flock(csv_file, fcntl.LOCK_UN)
