import argparse as ap
import os

LINK_LOCAL_MULTICAST = "FF02"


class Config:
    def __init__(self):
        parser = ap.ArgumentParser()

        parser.add_argument('-uid',
                            '--unique_identifier',
                            help="A unique 4 char hex identifier that can be used to avoid collisions with "
                                 "other multicast groups. The current users uid will be used if not supplied.",
                            default=get_default_id())

        parser.add_argument('-g', '--group_id', action='append',
                            help="Hex value between 0 and FFFF. This is used for the last 16 bits of the IPv6 "
                                 "multicast address, which is used in the overlay to isolate subnetworks, so "
                                 "an ILNP locator will map to this group id. Defaults to 0000 if not given. Multiple "
                                 "values can be given such that this node will bridge multiple networks.",
                            default='0000')

        parser.add_argument('-p', '--port',
                            help="Port number to be used for UDP socket binding. Defaults to 8080.",
                            default=8080)

        parser.add_argument('-hc', '--hop_count',
                            help="Number of hops to allow for each packet before being discarded. Defaults to 3",
                            default=3)

        parser.add_argument('-m', '--message',
                            help="Plaintext message to be sent as payload of ILNP packets. Defaults to 'Hello "
                                 "World!', of course.",
                            default="Hello World!")

        parser.add_argument('-s', '--sleep',
                            help="Time to sleep in seconds between this node sending packets to hosts. A value of -1 "
                                 "will disable these packets.")

        args = parser.parse_args()
        print "Node running with the following configuration:"
        print(args)

        self.uid = args.uid
        self.group_ids = args.g
        self.port = args.p
        self.hop_count = args.hc
        self.message = args.m
        self.sleep = args.s
        self.ipv6_multicast_addresses = [buildIPv6MulticastAddress(self.uid, group_id) for group_id in self.group_ids]


def buildIPv6MulticastAddress(uid, group_id):
    """Takes the unique identifer and multicast group id (locator) and produces the ipv6 multicast address for this 
    sub network """
    return (LINK_LOCAL_MULTICAST + "::" + uid + ":" + group_id).decode('utf-8')


def get_default_id():
    """Provides a unique identifier for the network by producing the hex value of the given users uid"""
    uid = os.getuid()
    return format(uid, 'x')
