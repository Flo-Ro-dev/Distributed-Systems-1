import time
import argparse
import sys
from peer_node import PeerNode

def main():
    parser = argparse.ArgumentParser(description="Distributed Mäxle Game Node")
    parser.add_argument("password", help="Shared password for the game group")
    args = parser.parse_args()

    # 1. Initialize Node
    node = PeerNode(password=args.password)
    node.start()

    # 2. Discovery Phase
    print("\n--- Phase 1: Discovery (10s) ---")
    print("Broadcasting presence...")
    node.broadcast_hello()
    
    # Progress bar for visual flair (optional)
    for _ in range(10):
        time.sleep(1)
        sys.stdout.write(".")
        sys.stdout.flush()
    print("\n")

    # 3. Topology Phase
    print("--- Phase 2: Building Ring ---")
    node.form_ring()
    time.sleep(2)

    # 4. Election Phase
    # Optimization: Only node with highest local IP starts election to reduce traffic
    # But for robustness, we just let the user trigger it or auto-start
    print("--- Phase 3: Election ---")
    # For demo purposes, we auto-start election
    node.start_election()

    # 5. Keep Alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[System] Shutting down node...")

if __name__ == "__main__":
    main()