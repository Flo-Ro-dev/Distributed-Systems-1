# peer_node.py

import socket
import threading
import time
import json
import uuid
import hashlib
import queue
from collections import deque
from game_logic import MaxleGame

# Configuration
DISCOVERY_TIME = 5
BROADCAST_PORT = 50000
TCP_PORT = 50001
BUF_SIZE = 4096

# Heartbeat Settings
HEARTBEAT_INTERVAL = 1.0
HEARTBEAT_TIMEOUT = 5.0
NETWORK_TIMEOUT_LIMIT = 15

# Reliability Settings
HISTORY_SIZE = 50

class PeerNode:
    def __init__(self, password):
        self.id = str(uuid.uuid4())[:8]
        self.password = password
        self.group_hash = hashlib.sha256(password.encode()).hexdigest()
        
        self.my_ip = self._detect_best_ip()
        self.broadcast_ip = self._calculate_broadcast(self.my_ip)
        
        self.max_strikes = 3
        self.scores = {} 
        self.running = True
        self.game_running = False
        self.is_leader = False
        self.is_spectator = False
        self.network_healthy = True 
        
        self.peers = {} 
        self.peer_last_seen = {} 
        self.ui_queue = queue.Queue()
        self.final_player_list = []
        self.alive_players = []
        
        self.neighbor_sock = None
        self.neighbor_id = None
        self.game_engine = MaxleGame(password)
        
        self.active_player_id = None 
        self.turn_state = "IDLE" 
        
        # --- State Management ---
        self.round_id = 1 
        self.my_seq = 0  
        self.remote_seqs = {}  
        self.holdback_queue = {}  
        self.msg_history = deque(maxlen=HISTORY_SIZE) 
        self.input_queue = queue.Queue()
        self._waiting_for_ip_log = False

        print(f"[Init] Node Started | ID: {self.id}")
        print(f"[Init] IP: {self.my_ip} | Broadcast Target: {self.broadcast_ip}")

    # --- NETWORK UTILITIES ---
    def _detect_best_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80)) 
            ip = s.getsockname()[0]
            s.close()
            return ip
        except: pass
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except: return '127.0.0.1'

    def _calculate_broadcast(self, ip):
        if ip == '127.0.0.1': return '255.255.255.255'
        parts = ip.split('.')
        return f"{parts[0]}.{parts[1]}.{parts[2]}.255"

    # --- MAIN LIFECYCLE ---
    def start(self):
        threading.Thread(target=self._listen_udp, daemon=True).start()
        threading.Thread(target=self._listen_tcp, daemon=True).start()

        self._phase_discovery()

        if self.game_running:
            print("[!] Found existing game. Joining as SPECTATOR.")
            self.is_spectator = True
            self._start_heartbeat_system()
            self._phase_game_loop()
            return

        self._phase_lobby()

        self.alive_players = list(self.final_player_list)
        self.game_running = True
        if self.final_player_list:
            self.active_player_id = self.final_player_list[0]

        self._start_heartbeat_system()
        self._connect_to_next_neighbor()
        self._phase_game_loop()

    def _start_heartbeat_system(self):
        threading.Thread(target=self._send_heartbeats, daemon=True).start()
        threading.Thread(target=self._monitor_liveness, daemon=True).start()

    def _send_heartbeats(self):
        while self.running and self.game_running:
            msg = {
                'type': 'HEARTBEAT',
                'state': 'RUNNING',
                'round_id': self.round_id,
                'players': self.alive_players,
                'scores': self.scores  # <--- ADD THIS
            }
            self._send_unreliable_broadcast(msg)
            time.sleep(HEARTBEAT_INTERVAL)

    def _monitor_liveness(self):
        while self.running and self.game_running:
            time.sleep(1)
            if len(self.alive_players) <= 1: continue

            now = time.time()
            dead_candidates = []
            
            for pid in list(self.alive_players):
                if pid == self.id: continue
                last = self.peer_last_seen.get(pid, now)
                # 5 second timeout
                if now - last > HEARTBEAT_TIMEOUT:
                    dead_candidates.append(pid)
            
            for dead_id in dead_candidates:
                if dead_id in self.alive_players:
                    print(f"\n[!!!] TIMEOUT: Player {dead_id} stopped responding.")
                    
                    # FIX: Broadcast multiple times to ensure delivery
                    msg = {'type': 'PLAYER_LEFT', 'dropout': dead_id}
                    for _ in range(3):
                        self._send_unreliable_broadcast(msg)
                        time.sleep(0.1)
                    
                    # Handle locally immediately
                    self._handle_player_left(dead_id)

    def _phase_discovery(self):
        print(f"\n--- PHASE 1: DISCOVERY ({DISCOVERY_TIME}s) ---")
        start_time = time.time()
        while time.time() - start_time < DISCOVERY_TIME:
            if self.game_running: break 
            self._send_unreliable_broadcast({
                'type': 'HELLO', 
                'current_seq': self.my_seq,
                'known_peers': list(self.peers.keys())
            })
            time.sleep(1)
        print(f"Peers found: {len(self.peers)}")

    def _phase_lobby(self):
        print("\n" + "="*50 + "\n LOBBY / ELECTION PHASE \n" + "="*50)
        def input_listener():
            while not self.game_running:
                try:
                    i = input()
                    self.input_queue.put(i)
                except: pass
        threading.Thread(target=input_listener, daemon=True).start()

        while not self.game_running:
            all_nodes = list(self.peers.keys()) + [self.id]
            all_nodes.sort()
            highest_id = all_nodes[-1]
            
            am_i_leader = (self.id == highest_id)

            if am_i_leader and not self.is_leader:
                print(f"\n[!!!] YOU BECAME LEADER (ID: {self.id})")
                print(">> Press ENTER to Start Game")
                self.is_leader = True
            elif not am_i_leader and self.is_leader:
                print(f"\n[---] DEMOTED: Higher ID {highest_id} found.")
                self.is_leader = False

            if self.is_leader:
                try:
                    if not self.input_queue.empty():
                        _ = self.input_queue.get() 
                        self._start_game_as_leader()
                        return
                except: pass
            else:
                try:
                    event = self.ui_queue.get(block=False)
                    if event['type'] == 'GAME_START':
                        self.final_player_list = event['players']
                        self.max_strikes = event['max_strikes']
                        
                        # FIX: Sync the active player from the message
                        self.active_player_id = event.get('starting_player', self.final_player_list[-1]) 
                        
                        for p in self.final_player_list: self.scores[p] = 0
                        print(f"\n[!] GAME STARTED by Leader. Active Player: {self.active_player_id}")
                        return
                except queue.Empty: pass

            self._send_unreliable_broadcast({
                'type': 'HELLO', 'current_seq': self.my_seq,
                'known_peers': list(self.peers.keys())
            })
            time.sleep(1)

    def _start_game_as_leader(self):
        current_list = list(self.peers.keys()) + [self.id]
        current_list.sort()
        if len(current_list) < 2:
            print("[!] Need at least 2 players!")
            return
        self.final_player_list = current_list
        self.max_strikes = 3
        
        # FIX: Explicitly tell everyone that I (the Leader) am starting
        msg = {
            'type': 'GAME_START', 
            'players': self.final_player_list, 
            'max_strikes': self.max_strikes,
            'starting_player': self.id  # <--- ADD THIS
        }
        self._send_reliable_broadcast(msg)
        
        for p in self.final_player_list: self.scores[p] = 0
        
        self.active_player_id = self.id # Set myself as active
        self.ui_queue.put({'type': 'MY_TURN_START', 'first_round': True})

    def _connect_to_next_neighbor(self):
        if self.is_spectator: return
        
        # 1. Determine who my neighbor SHOULD be
        try: my_idx = self.final_player_list.index(self.id)
        except ValueError: return 
        
        target_id = None
        for i in range(1, len(self.final_player_list)):
            cand = self.final_player_list[(my_idx + i) % len(self.final_player_list)]
            if cand in self.alive_players:
                target_id = cand
                break
        
        if not target_id or target_id == self.id: return

        # 2. Re-Route if current neighbor doesn't match target
        if self.neighbor_id != target_id:
            if self.neighbor_sock:
                print(f" [Network] Closing stale connection to {self.neighbor_id}...")
                try: self.neighbor_sock.close()
                except: pass
            self.neighbor_sock = None
            self.neighbor_id = target_id 

        # 3. Connect if needed
        if not self.neighbor_sock:
            target_ip = self.peers.get(target_id)
            if not target_ip: target_ip = '127.0.0.1' # Fallback
            
            print(f" [Network] Connecting to Ring Neighbor: {target_id} ({target_ip})...", end="")
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3.0) 
                s.connect((target_ip, TCP_PORT))
                s.settimeout(None)
                self.neighbor_sock = s
                print(" Success!")
            except:
                print(" Failed (will retry).")

    def _phase_game_loop(self):
        print("\n" + "*"*40 + "\n          GAME START          \n" + "*"*40)
        self._print_scoreboard()
        while self.running:
            try:
                event = self.ui_queue.get()
                
                if self.is_spectator and event['type'] in ['MY_TURN_START', 'TOKEN_RCV']:
                     continue

                if event['type'] == 'MY_TURN_START':
                    self.active_player_id = self.id
                    self._do_turn(event.get('first_round', False), event.get('prev_claim', 0))
                
                elif event['type'] == 'TOKEN_RCV':
                    token = event['token']
                    sender = token.get('sender_id')
                    
                    self.active_player_id = self.id 
                    self._handle_incoming_token(token)
                
                elif event['type'] == 'ANNOUNCE':
                    sender_id = event.get('sender_id')
                    if sender_id not in self.alive_players: continue
                    if event.get('round_id') != self.round_id: continue
                    
                    self.active_player_id = sender_id 
                    if sender_id != self.id:
                        print(f"\n [INFO] {sender_id} announced: {event.get('value')}")

                elif event['type'] == 'ROUND_OVER':
                    if event.get('round_id') == self.round_id:
                        self._handle_round_over(event)
                
                elif event['type'] == 'PLAYER_LEFT':
                    self._handle_player_left(event['dropout'])

            except KeyboardInterrupt: break

    def _handle_player_left(self, dropout_id):
        if dropout_id not in self.final_player_list: return
        
        # 1. Update Alive List & Score
        if dropout_id in self.alive_players:
            self.alive_players.remove(dropout_id)
        
        # Mark them as max strikes so they are effectively out logic-wise
        self.scores[dropout_id] = self.max_strikes
        print(f"\n[!] Player {dropout_id} ELIMINATED (Connection Lost).")

        # --- CRITICAL FIX: FORCE NEW ROUND ID ---
        # A crash voids the current round. Everyone must increment to agree on the future.
        self.round_id += 1 
        # ----------------------------------------

        # 2. Topology Repair
        if not self.is_spectator and self.neighbor_id == dropout_id:
            print(f" [Network] Neighbor {dropout_id} gone. Repairing ring...")
            if self.neighbor_sock:
                try: self.neighbor_sock.close()
                except: pass
            self.neighbor_sock = None
            self.neighbor_id = None
            self._connect_to_next_neighbor()

        # 3. Check Win Condition
        if len(self.alive_players) <= 1:
            if len(self.alive_players) == 1:
                print(f"\n[GAME OVER] WINNER IS {self.alive_players[0]}!")
            self.running = False
            self.game_running = False
            self._print_scoreboard()
            return

        # 4. RECOVERY: Calculate Successor
        idx = 0
        if dropout_id in self.final_player_list:
            idx = self.final_player_list.index(dropout_id)
        
        successor = None
        for i in range(1, len(self.final_player_list)):
            cand = self.final_player_list[(idx + i) % len(self.final_player_list)]
            if cand in self.alive_players:
                successor = cand
                break
        
        if successor:
            self.active_player_id = successor
            
            if successor == self.id:
                print(f"\n[!] RECOVERY: It is YOUR turn to start a new round. Press ENTER to continue.")
                self.turn_state = "IDLE"
                time.sleep(1.0)
                
                # --- FIX: FLUSH QUEUE & FORCE FRESH START ---
                # Remove any stale inputs or token receipts from the now-dead round
                while not self.ui_queue.empty():
                    try: self.ui_queue.get_nowait()
                    except: break
                
                self.ui_queue.put({
                    'type': 'MY_TURN_START', 
                    'first_round': True, 
                    'prev_claim': 0,
                    'round_id_sync': self.round_id # Internal marker
                })
            else:
                print(f"[!] Waiting for {successor} to start new round...")
        
        self._print_scoreboard()

    def _handle_incoming_token(self, token):
        sender_id = token.get('sender_id')
        if sender_id == self.id: return
        
        # Initial liveness check
        if sender_id not in self.alive_players: 
            print("[!] Ignoring token from dead player.")
            return

        announced_val = token['announced']
        print(f"\n[INCOMING] Claim: {announced_val}")

        # --- LOGIC BLOCK: CHECK FOR DEAD SENDER AFTER INPUT ---
        def is_sender_still_valid():
            if sender_id not in self.alive_players:
                print("\n[!] Sender died while you were deciding. Turn VOID.")
                return False
            # Also check if round ID advanced (due to recovery) while we were waiting
            if token.get('round_id') != self.round_id:
                print("\n[!] Round ID changed (Recovery happened). Turn VOID.")
                return False
            return True

        if announced_val == 21:
            print(f"[!!!] MÄXLE (21) ANNOUNCED by {sender_id}!")
            print("      Options: (y) Trust, (n) Check")
            
            while True:
                cmd = input(">> Decision (y/n)? ").lower()
                if cmd in ['y', 'n']: break
            
            # --- CRITICAL CHECK ---
            if not is_sender_still_valid(): return
            # ----------------------

            real = token['security']['hidden_real']
            
            if cmd == 'y':
                loser = self.id
                points = 1
                print(f"   [ACCEPTED] You took the hit. Real was: {real}")
            else:
                if real == 21:
                    loser = self.id
                    points = 2
                    print(f"   [FAILED CHECK] It was a MÄXLE! You take 2 strikes.")
                else:
                    loser = sender_id
                    points = 2
                    print(f"   [BUSTED] {sender_id} lied! They take 2 strikes. Real: {real}")
            
            # (Round over logic remains the same...)
            round_over_msg = {
                'type': 'ROUND_OVER', 'loser': loser, 'real_value': real,
                'points': points, 'round_id': self.round_id
            }
            self._send_reliable_broadcast(round_over_msg)
            self.ui_queue.put(round_over_msg)
            return

        # Normal value logic
        cmd = input(">> Trust (y) or Check (n)? ").lower()
        
        # --- CRITICAL CHECK ---
        if not is_sender_still_valid(): return
        # ----------------------

        if cmd == 'n':
            real = token['security']['hidden_real']
            loser = sender_id if real != announced_val else self.id
            print(f"   [RESULT] Real: {real} | Loser: {loser}")
            
            round_over_msg = {
                'type': 'ROUND_OVER', 'loser': loser, 'real_value': real,
                'points': 1, 'round_id': self.round_id
            }
            self._send_reliable_broadcast(round_over_msg)
            self.ui_queue.put(round_over_msg)
        else:
            self._do_turn(False, announced_val)

    def _handle_round_over(self, msg):
        self.turn_state = "IDLE"
        loser = msg['loser']
        
        if loser not in self.scores: self.scores[loser] = 0
        self.scores[loser] += msg.get('points', 1)
        self.round_id += 1

        # Check for Elimination
        if self.scores[loser] >= self.max_strikes:
            print(f"[!] {loser} ELIMINATED.")
            if loser in self.alive_players: 
                self.alive_players.remove(loser)
            
            # If I just lost, switch to spectator
            if loser == self.id:
                print(">> YOU ARE OUT. SPECTATOR MODE.")
                self.is_spectator = True
                if self.neighbor_sock: 
                    try: self.neighbor_sock.close()
                    except: pass
                    self.neighbor_sock = None
                self._print_scoreboard()
                return 

            # Force topology update immediately if my neighbor died
            if self.neighbor_id == loser: 
                self._connect_to_next_neighbor()

        self._print_scoreboard()

        # Check for Game Winner
        if len(self.alive_players) == 1:
            print(f"\n[GAME OVER] WINNER IS {self.alive_players[0]}!")
            self.running = False
            return

        # Calculate Next Player (Strictly skipping dead people)
        # Usually, the loser starts the next round. If dead, the person AFTER them starts.
        start_node = loser
        idx = 0
        if start_node in self.final_player_list: 
            idx = self.final_player_list.index(start_node)
        
        next_p = None
        # Start looking from the loser (offset 0) or loser+1? 
        # Maxle rule: Loser starts. If loser is dead, next guy starts.
        offset = 0 
        
        for i in range(offset, len(self.final_player_list) + 1):
            cand = self.final_player_list[(idx + i) % len(self.final_player_list)]
            if cand in self.alive_players:
                next_p = cand
                break
        
        if not next_p: return # Should not happen if len > 1

        self.active_player_id = next_p
        
        if next_p == self.id and not self.is_spectator:
            print("\n[!] Your turn to start next round.")
            time.sleep(2)
            # Reset prev_claim to 0 because it's a fresh round
            self.ui_queue.put({'type': 'MY_TURN_START', 'first_round': True, 'prev_claim': 0})
        else:
            print(f"\n[!] Waiting for {next_p}...")

    def _do_turn(self, first_round, prev_claim):
        if self.is_spectator: return 
        print("\n--- YOUR TURN ---")
        
        # Only ask to roll if it's NOT the first round (Normal play)
        if not first_round: 
            input(">> Press ENTER to roll dice...")
            
        val = self.game_engine.roll_dice()
        print(f"   [HIDDEN ROLL] {val}")
        
        while True:
            try:
                # If first_round is True, min_val MUST be 0
                min_val = prev_claim if not first_round else 0
                
                claim = int(input(f">> Announce (> {min_val}): "))
                is_valid, err = self.game_engine.validate_announcement(claim, min_val)
                if is_valid: break
                print(f"   [!] {err}")
            except: pass

        self._send_reliable_broadcast({
            'type': 'ANNOUNCE', 
            'value': claim, 
            'sender_id': self.id,
            'round_id': self.round_id
        })
        
        token = self.game_engine.secure_cup(val, claim)
        token['round_id'] = self.round_id
        
        while self.running and self.game_running:
            if len(self.alive_players) < 2: return

            if self._send_tcp_token_with_ack(token):
                return 
            
            if self.neighbor_sock:
                print(f"[!] Connection failed with {self.neighbor_id}. Retrying...")
                try: self.neighbor_sock.close()
                except: pass
                self.neighbor_sock = None
            
            self._connect_to_next_neighbor()
            time.sleep(2)

    def _send_tcp_token_with_ack(self, token):
        if self.is_spectator: return False
        if not self.neighbor_sock: self._connect_to_next_neighbor()
        if not self.neighbor_sock: return False
        
        token['sender_id'] = self.id
        msg = json.dumps({'type': 'TOKEN', 'payload': token}) + "\n"
        try:
            self.neighbor_sock.sendall(msg.encode())
            print(f">> Cup passed to {self.neighbor_id}...")
            
            response_bytes = self.neighbor_sock.recv(1024)
            if not response_bytes: return False
            response = json.loads(response_bytes.decode())
            
            # --- FIX: Check if peer explicitly accepted or rejected ---
            if response.get('status') == 'REJECTED':
                print(f"[!] Peer REJECTED the cup: {response.get('reason')}")
                return False
            # ---------------------------------------------------------
            
            return response.get('type') == 'ACK'
        except (socket.timeout, socket.error, json.JSONDecodeError):
            return False

    def _listen_udp(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: s.bind(('', BROADCAST_PORT))
        except: return
        
        while self.running:
            try:
                data, addr = s.recvfrom(BUF_SIZE)
                msg = json.loads(data.decode())
                if msg.get('group') != self.group_hash: continue
                
                sid = msg.get('sender_id')
                sip = msg.get('sender_ip', addr[0])
                if sid == self.id: continue
                
                # --- STRICT IP UPDATE ---
                self.peer_last_seen[sid] = time.time()
                if sid not in self.peers or self.peers[sid] != sip:
                    self.peers[sid] = sip
                # ------------------------

                if msg['type'] == 'HEARTBEAT':
                    if msg.get('state') == 'RUNNING':
                        self.game_running = True 
                        
                        # --- FIX: SYNC SCORES ---
                        # If the heartbeat contains scores, update our local record.
                        # This ensures spectators or late-joiners see the correct history.
                        if 'scores' in msg:
                            remote_scores = msg['scores']
                            for p, score in remote_scores.items():
                                # We trust the network's score if it's higher than ours,
                                # or if we are a spectator (trust everything).
                                if self.is_spectator or score > self.scores.get(p, 0):
                                    self.scores[p] = score
                        # ------------------------

                        if self.is_spectator or not self.final_player_list:
                            # (Existing logic for updating round_id and alive_players...)
                            if 'round_id' in msg and msg['round_id'] > self.round_id:
                                self.round_id = msg['round_id']
                            
                            if 'players' in msg:
                                self.alive_players = msg['players']
                                if not self.final_player_list:
                                    self.final_player_list = self.alive_players
                                    
                                    for p in self.final_player_list:
                                        if p not in self.scores: self.scores[p] = 0
                    continue

                if msg['type'] == 'HELLO':
                    for friend_id in msg.get('known_peers', []):
                        if friend_id != self.id and friend_id not in self.peers:
                            self.peers[friend_id] = None 
                    continue

                if msg['type'] == 'NACK':
                    self._handle_nack(msg['req_seq'])
                    continue

                if 'seq' not in msg: continue

                seq = msg['seq']
                expected = self.remote_seqs.get(sid, 0) + 1

                if seq == expected:
                    self.remote_seqs[sid] = seq
                    self.ui_queue.put(msg)
                    while True:
                        next_seq = self.remote_seqs[sid] + 1
                        if sid in self.holdback_queue and next_seq in self.holdback_queue[sid]:
                            queued_msg = self.holdback_queue[sid].pop(next_seq)
                            self.remote_seqs[sid] = next_seq
                            self.ui_queue.put(queued_msg)
                        else: break
                
                elif seq > expected:
                    if sid not in self.holdback_queue: self.holdback_queue[sid] = {}
                    self.holdback_queue[sid][seq] = msg
                    for missing in range(expected, seq):
                        self._send_nack(sid, missing)
            except: pass

    def _listen_tcp(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', TCP_PORT))
        s.listen(5)
        while self.running:
            try:
                conn, _ = s.accept()
                threading.Thread(target=self._handle_tcp_stream, args=(conn,), daemon=True).start()
            except: pass

    def _handle_tcp_stream(self, conn):
        with conn:
            for line in conn.makefile('r', encoding='utf-8'):
                try:
                    data = json.loads(line)
                    if data['type'] == 'TOKEN':
                        token = data['payload']
                        sender = token.get('sender_id')
                        
                        # --- VALIDATION (Send Application NACK if failed) ---
                        reason = None
                        if sender == self.id: reason = "Loopback"
                        elif sender not in self.alive_players: reason = "Sender Dead"
                        elif token.get('round_id') != self.round_id: 
                            reason = f"Round Mismatch (Msg:{token.get('round_id')} != Me:{self.round_id})"
                        
                        if reason:
                            print(f"\n[DEBUG] REJECTED TOKEN: {reason}")
                            conn.sendall(json.dumps({'type': 'ACK', 'status': 'REJECTED', 'reason': reason}).encode())
                        else:
                            conn.sendall(json.dumps({'type': 'ACK', 'status': 'OK'}).encode())
                            if not self.is_spectator:
                                self.ui_queue.put({'type': 'TOKEN_RCV', 'token': token})
                        # ----------------------------------------------------

                except: pass
    
    def _print_scoreboard(self):
        print("\n--- SCOREBOARD ---")
        for p in self.final_player_list:
            score = self.scores.get(p, 0)
            status = "ALIVE" if p in self.alive_players else "DEAD"
            print(f" {p}: {score}/{self.max_strikes} [{status}]")
        print("------------------")

    def _send_reliable_broadcast(self, msg):
        self.my_seq += 1
        msg['seq'] = self.my_seq
        self.msg_history.append(msg)
        self._send_unreliable_broadcast(msg)

    def _send_unreliable_broadcast(self, msg):
        msg.update({'group': self.group_hash, 'sender_id': self.id, 'sender_ip': self.my_ip})
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(json.dumps(msg).encode(), (self.broadcast_ip, BROADCAST_PORT))
        except: pass

    def _handle_nack(self, req_seq):
        for stored_msg in self.msg_history:
            if stored_msg['seq'] == req_seq:
                self._send_unreliable_broadcast(stored_msg) 
                return

    def _send_nack(self, target_id, missing_seq):
        nack = {'type': 'NACK', 'req_seq': missing_seq, 'target_id': target_id}
        self._send_unreliable_broadcast(nack)