import socket
import threading
import time
import json
import uuid
import hashlib
import random

# Configuration
BROADCAST_PORT = 50000
TCP_PORT = 50001
BUFFER_SIZE = 1024

class MaxleNode:
    def __init__(self, password):
        self.node_id = str(uuid.uuid4())
        self.peers = {} 
        self.running = True
        
        self.group_id = hashlib.sha256(password.encode('utf-8')).hexdigest()
        
        print(f"[*] Node started. ID: {self.node_id[:8]}")
        
        # Start Listeners
        threading.Thread(target=self.listen_discovery, daemon=True).start()
        threading.Thread(target=self.listen_tcp, daemon=True).start()

    def get_my_ip(self):
        """ Modified to prioritize 10.x.x.x IPs for your namespace testbed """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Try to connect to a dummy 10.x address to force the OS to give us the 10.x interface
            s.connect(('10.255.255.255', 1)) 
            IP = s.getsockname()[0]
        except Exception:
            try:
                # Fallback to standard Google DNS check
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 80))
                IP = s.getsockname()[0]
            except Exception:
                IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def listen_discovery(self):
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            udp_sock.bind(('', BROADCAST_PORT))
        except OSError:
            print("[!] Critical: UDP Port in use. Kill old processes!")
            return

        print("[*] Listening for discovery broadcasts...")
        while self.running:
            try:
                data, addr = udp_sock.recvfrom(BUFFER_SIZE)
                msg = json.loads(data.decode())
                
                if msg.get('group_id') == self.group_id and msg['node_id'] != self.node_id:
                    if msg['type'] == 'DISCOVERY':
                        if msg['node_id'] not in self.peers:
                            print(f"[+] Discovered new peer: {addr[0]}")
                            self.peers[msg['node_id']] = addr[0]
                            self.send_udp_direct(addr[0], 'PONG')
                    elif msg['type'] == 'PONG':
                        if msg['node_id'] not in self.peers:
                            print(f"[+] Peer responded: {addr[0]}")
                            self.peers[msg['node_id']] = addr[0]
            except Exception as e:
                print(f"[!] Discovery Error: {e}")

    def broadcast_presence(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        message = json.dumps({
            'type': 'DISCOVERY', 'node_id': self.node_id, 'group_id': self.group_id 
        })
        sock.sendto(message.encode(), ('<broadcast>', BROADCAST_PORT))

    def send_udp_direct(self, ip, msg_type):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        message = json.dumps({
            'type': msg_type, 'node_id': self.node_id, 'group_id': self.group_id
        })
        sock.sendto(message.encode(), (ip, BROADCAST_PORT))

    def listen_tcp(self):
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            tcp_sock.bind(('', TCP_PORT))
        except OSError:
            print("[!] Critical: TCP Port in use. Kill old processes!")
            return
            
        tcp_sock.listen(5)
        while self.running:
            conn, addr = tcp_sock.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()

    def handle_client(self, conn, addr):
        print(f"[+] Connection accepted from {addr}")
        while self.running:
            try:
                data = conn.recv(BUFFER_SIZE)
                if not data: break
                
                raw_msg = data.decode()
                # Stacked Packet Fix
                parts = raw_msg.split('}')
                for part in parts:
                    if part.strip():
                        try:
                            # Re-add brace if missing due to split
                            fixed_json = part if part.endswith('}') else part + '}'
                            msg = json.loads(fixed_json)
                            self.process_message(msg)
                        except json.JSONDecodeError:
                            pass 
            except Exception as e:
                print(f"[!] Connection error: {e}")
                break
        conn.close()

    def process_message(self, msg):
        m_type = msg.get('type')
        if m_type == 'ELECTION':
            self.handle_election_vote(msg)
        elif m_type == 'COORDINATOR':
            self.handle_coordinator(msg)
        elif m_type == 'GAME_TOKEN':
            self.handle_game_turn(msg)

    def form_ring(self):
        print("[*] Forming Ring...")
        all_nodes = []
        my_ip = self.get_my_ip() 
        all_nodes.append((my_ip, self.node_id))
        
        for pid, pip in self.peers.items():
            all_nodes.append((pip, pid))
            
        all_nodes.sort()
        
        my_index = -1
        for i, (ip, nid) in enumerate(all_nodes):
            if nid == self.node_id:
                my_index = i
                break
        
        neighbor_index = (my_index + 1) % len(all_nodes)
        neighbor_ip, neighbor_id = all_nodes[neighbor_index]
        
        print(f"[*] My Neighbor is: {neighbor_ip} (ID: {neighbor_id[:8]})")
        self.connect_to_neighbor(neighbor_ip)

    def connect_to_neighbor(self, ip):
        try:
            self.next_neighbor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            for _ in range(5):
                try:
                    self.next_neighbor_socket.connect((ip, TCP_PORT))
                    print(f"[+] Connected to neighbor {ip}")
                    return
                except ConnectionRefusedError:
                    time.sleep(1)
            print(f"[!] Could not connect to neighbor {ip}")
        except Exception as e:
            print(f"[!] Error connecting: {e}")

    def send_to_neighbor(self, message):
        # ... (wait for connection logic stays the same) ...
        retries = 0
        while not hasattr(self, 'next_neighbor_socket') or self.next_neighbor_socket is None:
             # ... (existing retry loop) ...
             time.sleep(0.5)
             retries += 1
             if retries > 5: break # Don't wait forever

        try:
            self.next_neighbor_socket.send(json.dumps(message).encode())
            time.sleep(0.1)
        except Exception as e:
            print(f"[!] Failed to send to neighbor: {e}")
            # --- NEW: Trigger Repair ---
            self.repair_ring()

    # --- VOTING ---
    def start_election(self):
        print("[!] Starting Election Process...")
        self.participant = True
        msg = {'type': 'ELECTION', 'candidate_id': self.node_id}
        self.send_to_neighbor(msg)

    def handle_election_vote(self, msg):
        candidate = msg['candidate_id']
        
        if candidate > self.node_id:
            self.participant = True
            self.send_to_neighbor(msg)
        elif candidate < self.node_id:
            if not getattr(self, 'participant', False):
                self.start_election()
        elif candidate == self.node_id:
            print("[!!!] ELECTION WON. I am the Leader.")
            self.is_leader = True
            self.participant = False
            coord_msg = {'type': 'COORDINATOR', 'leader_id': self.node_id}
            self.send_to_neighbor(coord_msg)
            time.sleep(2)
            self.start_new_round()

    def handle_coordinator(self, msg):
        self.participant = False
        self.leader_id = msg['leader_id']
        if self.leader_id != self.node_id:
            print(f"[*] New Leader Elected: {self.leader_id[:8]}")
            self.send_to_neighbor(msg)

    # --- GAME LOGIC ---
    def start_new_round(self):
        """ Only the Leader calls this to put the 'Cup' into the ring """
        print("\n" + "="*40)
        print("[!!!] YOU ARE THE LEADER!")
        print("You hold the cup. The game waits for you.")
        
        # --- INTERACTIVE PAUSE ---
        input(">> Press ENTER to generate the first cup and start the game...")
        # -------------------------
        
        print("[Game] Generating new fresh cup...")
        initial_token = {
            'type': 'GAME_TOKEN',
            'turn_count': 0,
            'last_announced_value': 0,
            'actual_dice_value': 0,
            'message': 'Game Start!'
        }
        self.handle_game_turn(initial_token)

    def handle_game_turn(self, token):
        print("\n" + "="*40)
        print(f"[*] IT IS MY TURN! (Round {token['turn_count']})")
        
        if token['last_announced_value'] > 0:
            print(f"[*] Previous player announced: {token['last_announced_value']}")
            # In a real game, you would ask: input("Type 'trust' or 'check': ")
        
        # --- INTERACTIVE PAUSE ---
        # The code stops here. The network connection is held open.
        # The game effectively "pauses" at this computer until you type.
        user_input = input(">> Type anything to roll the dice: ")
        # -------------------------
        
        # 1. Roll Dice
        import random
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        
        # Maxle Logic: Higher number first.
        if d1 < d2: d1, d2 = d2, d1
        real_value = int(f"{d1}{d2}")
        
        print(f"[*] You rolled: {real_value}")
        
        # 2. Auto-Bluff Logic (to keep it simple for now)
        # If we didn't beat the previous score, we lie.
        announced_value = real_value
        if announced_value <= token['last_announced_value']:
             announced_value = token['last_announced_value'] + 1 
             print(f"[*] You rolled too low! Auto-bluffing to: {announced_value}")
        else:
             print(f"[*] You beat the score! Announcing truth: {announced_value}")
        
        # 3. Update Token
        token['last_announced_value'] = announced_value
        token['actual_dice_value'] = real_value
        token['turn_count'] += 1
        
        print("[*] Passing cup to neighbor...")
        self.send_to_neighbor(token)

    def repair_ring(self):
        """
        Called when a message fails to send.
        Finds the next alive node in the sorted list and connects to it.
        """
        print("\n[!] DETECTED NEIGHBOR FAILURE! Initiating Repair...")
        
        # 1. Re-calculate the ring to find the next valid neighbor
        all_nodes = []
        my_ip = self.get_my_ip()
        all_nodes.append((my_ip, self.node_id))
        for pid, pip in self.peers.items():
            all_nodes.append((pip, pid))
        all_nodes.sort()

        # Find where I am
        my_index = -1
        for i, (ip, nid) in enumerate(all_nodes):
            if nid == self.node_id:
                my_index = i
                break
        
        # 2. Iterate through potential neighbors until one connects
        # Start from my_index + 1
        total_nodes = len(all_nodes)
        
        for i in range(1, total_nodes):
            # Calculate next index, wrapping around
            next_idx = (my_index + i) % total_nodes
            candidate_ip, candidate_id = all_nodes[next_idx]
            
            # Skip myself
            if candidate_id == self.node_id:
                continue
                
            print(f"[*] Trying to bypass dead node. Connecting to: {candidate_ip}...")
            
            # Try to connect
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2) # Short timeout for repair
                sock.connect((candidate_ip, TCP_PORT))
                
                # Success! We found a live node.
                print(f"[+] Ring Repaired! New neighbor is {candidate_ip}")
                self.next_neighbor_socket = sock
                
                # 3. CRITICAL: The Token is lost. We must restart the game.
                # We do this by triggering a new election.
                print("[!] Token lost in crash. Triggering Emergency Election...")
                threading.Thread(target=self.start_election, daemon=True).start()
                return
                
            except (socket.error, socket.timeout):
                print(f"[-] Node {candidate_ip} is also unreachable.")
        
        print("[!] CRITICAL: I seem to be the only node left.")

if __name__ == "__main__":
    import sys
    pwd = sys.argv[1] if len(sys.argv) > 1 else "default_room"
    node = MaxleNode(password=pwd)
    
    time.sleep(1)
    
    print("--- Discovery Phase (10s) ---")
    node.broadcast_presence()
    time.sleep(10)
    
    node.form_ring()
    time.sleep(2)

    print("--- Starting Election ---")
    node.start_election()
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")