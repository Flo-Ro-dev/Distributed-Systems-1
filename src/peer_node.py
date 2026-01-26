import socket
import threading
import time
import json
import uuid
import hashlib
from game_logic import MaxleGame

# Network Constants
BROADCAST_PORT = 50000
TCP_PORT = 50001
BUF_SIZE = 1024

class PeerNode:
    def __init__(self, password):
        self.id = str(uuid.uuid4())
        self._running = True
        self.peers = {} # map: id -> ip
        
        # Security: Group isolation via hash
        self.group_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Network State
        self.right_neighbor = None  # Socket to the next node
        self.is_leader = False
        
        # Game State
        self.game_engine = MaxleGame()
        
        print(f"Node Initialized | ID: {self.id[:6]} | Group: {self.group_hash[:6]}")

    def start(self):
        """Starts all background listeners."""
        t_udp = threading.Thread(target=self._listen_discovery, daemon=True)
        t_tcp = threading.Thread(target=self._listen_tcp, daemon=True)
        t_udp.start()
        t_tcp.start()

    # --- Discovery Layer (UDP) ---
    def broadcast_hello(self):
        """sends a UDP broadcast to find other peers."""
        self._send_udp_msg('<broadcast>', 'HELLO')

    def _listen_discovery(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('', BROADCAST_PORT))
        except OSError:
            print("Error: UDP Port busy. Check running processes.")
            return

        while self._running:
            try:
                data, addr = sock.recvfrom(BUF_SIZE)
                msg = json.loads(data.decode())
                
                # Filter by group password
                if msg.get('group') != self.group_hash: continue
                if msg['sender_id'] == self.id: continue

                self._handle_discovery_msg(msg, addr[0])
            except Exception:
                pass

    def _handle_discovery_msg(self, msg, ip):
        sender = msg['sender_id']
        mtype = msg['type']

        if mtype == 'HELLO':
            if sender not in self.peers:
                print(f"[Net] Found peer: {ip}")
                self.peers[sender] = ip
                self._send_udp_msg(ip, 'WELCOME')
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if target_ip == '<broadcast>':
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        payload = json.dumps({
            'type': mtype,
            'sender_id': self.id,
            'group': self.group_hash
        })
        sock.sendto(payload.encode(), (target_ip, BROADCAST_PORT))

    # --- Topology Layer (Ring Formation) ---
    def form_ring(self):
        """Sorts peers by IP and connects to the immediate right neighbor."""
        print("[System] Calculating ring topology...")
        
        # 1. Gather all nodes (Self + Peers)
        my_ip = self._get_local_ip()
        node_list = [(my_ip, self.id)]
        for pid, pip in self.peers.items():
            node_list.append((pip, pid))
        
        # 2. Sort to ensure consistent order across all nodes
        node_list.sort()
        
        # 3. Find neighbor
        my_idx = -1
        for i, (ip, nid) in enumerate(node_list):
            if nid == self.id:
                my_idx = i
                break
        
        next_idx = (my_idx + 1) % len(node_list)
        target_ip, target_id = node_list[next_idx]
        
        print(f"[System] Ring Position: {my_idx}/{len(node_list)}. Neighbor -> {target_ip}")
        self._connect_neighbor(target_ip)

    def _connect_neighbor(self, ip):
        """Reliable connection attempt with retries."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            for i in range(3):
                try:
                    sock.connect((ip, TCP_PORT))
                    sock.settimeout(None) # Remove timeout for blocking mode
                    self.right_neighbor = sock
                    print(f"[Net] Connected to Ring Neighbor: {ip}")
                    return
                except (ConnectionRefusedError, socket.timeout):
                    time.sleep(1)
            print(f"[Err] Failed to connect to {ip}")
        except Exception as e:
            print(f"[Err] Socket error: {e}")

    # --- Communication Layer (TCP) ---
    def _listen_tcp(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', TCP_PORT))
        sock.listen(5)
        
        while self._running:
            client, addr = sock.accept()
            # Spawn thread for each incoming connection (Previous neighbor)
            threading.Thread(target=self._handle_incoming_stream, args=(client,), daemon=True).start()

    def _handle_incoming_stream(self, conn):
        with conn:
            while self._running:
                try:
                    data = conn.recv(BUF_SIZE)
                    if not data: break
                    
                    # Packet reassembly logic (handling stickiness)
                    raw = data.decode()
                    for packet in raw.split('}'):
                        if packet.strip():
                            fixed = packet + ('}' if not packet.endswith('}') else '')
                            try:
                                msg = json.loads(fixed)
                                self._dispatch_message(msg)
                            except json.JSONDecodeError:
                                pass
                except Exception:
                    break

    def _dispatch_message(self, msg):
        """Routing logic for incoming messages."""
        mtype = msg.get('type')
        
        if mtype == 'ELECTION':
            self._handle_election(msg)
        elif mtype == 'COORDINATOR':
            self._handle_coordinator(msg)
        elif mtype == 'TOKEN':
            self._handle_game_token(msg)

    def send_next(self, msg):
        """Sends data to the right neighbor. Triggers repair if fails."""
        if not self.right_neighbor:
            print("[Err] No neighbor connected.")
            self.repair_topology()
            return

        try:
            payload = json.dumps(msg)
            self.right_neighbor.sendall(payload.encode())
        except Exception:
            print("[Err] Link broken. Initiating Repair.")
            self.repair_topology()

    # --- Election Logic (Chang & Roberts) ---
    def start_election(self):
        print("[Election] starting candidacy...")
        self.participant = True
        self.send_next({'type': 'ELECTION', 'candidate': self.id})

    def _handle_election(self, msg):
        other_id = msg['candidate']
        if other_id > self.id:
            # They are better, forward it
            self.participant = True
            self.send_next(msg)
        elif other_id < self.id:
            # I am better. If I'm not running yet, start.
            if not getattr(self, 'participant', False):
                self.start_election()
        elif other_id == self.id:
            # It circled back. I won.
            print("[Election] VICTORY. I am the Leader.")
            self.is_leader = True
            self.participant = False
            self.send_next({'type': 'COORDINATOR', 'leader': self.id})
            
            # Start the game interaction
            time.sleep(1)
            self.init_game()

    def _handle_coordinator(self, msg):
        self.participant = False
        leader = msg['leader']
        if leader != self.id:
            print(f"[Election] New Leader: {leader[:6]}")
            self.send_next(msg)

    # --- Game Interaction ---
    def init_game(self):
        print("\n" + "="*40)
        print("LEADER ACTION REQUIRED")
        input(">> Press ENTER to create the Dice Cup and start: ")
        
        token = self.game_engine.generate_fresh_cup()
        token['type'] = 'TOKEN'
        self._handle_game_token(token) # Treat it as if I just received it

    def _handle_game_token(self, token):
        print("\n" + "-"*30)
        print(f"YOUR TURN (Round {token['turn_count']})")
        if token['last_announced'] > 0:
            print(f"Previous claim: {token['last_announced']}")
        
        # Interactive Pause
        input(">> Press ENTER to roll dice... ")
        
        # Delegate logic to the Game Engine
        updated_token = self.game_engine.play_turn(token)
        updated_token['type'] = 'TOKEN'
        
        print("Passing cup...")
        time.sleep(1) # Dramatic effect
        self.send_next(updated_token)

    # --- Fault Tolerance ---
    def repair_topology(self):
        """Self-healing logic: Finds next available peer."""
        print("[System] Repairing Ring...")
        # (Simplified for brevity: Logic identical to previous version, 
        # just sorting peer list and trying connect one by one)
        # ... [Insert your repair logic here] ...
        # After repair, trigger election:
        threading.Thread(target=self.start_election, daemon=True).start()

    def _get_local_ip(self):
        # Helper to get 10.x.x.x IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('10.255.255.255', 1))
            return s.getsockname()[0]
        except:
            return '127.0.0.1'
        elif mtype == 'WELCOME':
            if sender not in self.peers:
                print(f"[Net] Peer welcomed us: {ip}")
                self.peers[sender] = ip

    def _send_udp_msg(self, target_ip, mtype):
        sock = 