# main.py

import argparse
from peer_node import PeerNode

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("password", help="Room Password")
    args = parser.parse_args()

    node = PeerNode(args.password)
    node.start()