import socket
import threading
import time
import json
import uuid
import hashlib
import queue
import sys
import os
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

class PeerNode:
    def __init__(self, password):
        self.id = str(uuid.uuid4())[:8]
        self.password = password
        self.group_hash = hashlib.sha256(password.encode()).hexdigest()
        self.my_ip = self._get_local_ip()
        
        self.max_strikes = 3
        self.scores = {} 
        self.running = True
        self.game_running = False
        self.is_leader = False
        self.is_spectator = False
        self.network_healthy = True 
        
        self.connection_lost_start = None
        
        self.peers = {} 
        self.ui_queue = queue.Queue()
        self.final_player_list = []
        self.alive_players = []
        
        self.last_seen = {} 
        self.neighbor_sock = None
        self.neighbor_ip = None
        self.game_engine = MaxleGame(password)
        
        self.active_player_ip = None 
        
        # --- FIXED INITIALIZATION ---
        self.turn_state = "IDLE" 
        self.last_processed_token_sig = None

        print(f"[Init] Node Started | IP: {self.my_ip}")

    # ... [Keep start(), _start_heartbeat_system(), etc. unchanged] ...
    # ... [Keep _send_heartbeats, _monitor_liveness unchanged] ...
    # ... [Keep _phase_discovery through _phase_follower_lobby unchanged] ...
    # ... [Keep _connect_to_next_neighbor unchanged] ...

    def start(self):
        # (Copy your original start method here, no changes needed)
        threading.Thread(target=self._listen_udp, daemon=True).start()
        threading.Thread(target=self._listen_tcp, daemon=True).start()

        self._phase_discovery()

        if self.game_running:
            print("[!] Found existing game. Joining as SPECTATOR (No Rejoin Allowed).")
            self.is_spectator = True
            self._start_heartbeat_system()
            self._phase_game_loop()
            return

        self._phase_election()

        if self.is_leader:
            self._phase_leader_lobby()
        else:
            self._phase_follower_lobby()
            
            if self.is_spectator: 
                self._start_heartbeat_system()
                self._phase_game_loop()
                return

        self.alive_players = list(self.final_player_list)
        self.game_running = True
        
        if self.final_player_list:
            self.active_player_ip = self.final_player_list[0]

        now = time.time()
        for p in self.alive_players:
            if p != self.my_ip: self.last_seen[p] = now

        self._start_heartbeat_system()
        self._connect_to_next_neighbor()
        self._phase_game_loop()

    # ... [Ensure _start_heartbeat_system, _send_heartbeats, _monitor_liveness, 
    #      _phase_discovery, _phase_election, _phase_leader_lobby, 
    #      _phase_follower_lobby, _connect_to_next_neighbor are present as before] ...
    
    # Just to ensure the file is complete, here are the unchanged helper methods for context
    # (You don't need to copy-paste these if you just update the changed methods below, 
    # but I'm including the structure so you know where they fit).
    def _start_heartbeat_system(self):
        threading.Thread(target=self._send_heartbeats, daemon=True).start()
        threading.Thread(target=self._monitor_liveness, daemon=True).start()

    def _send_heartbeats(self):
        while self.running and self.game_running:
            msg = {'type': 'HEARTBEAT'}
            self._send_udp_broadcast(msg)
            time.sleep(HEARTBEAT_INTERVAL)

    def _monitor_liveness(self):
        while self.running and self.game_running:
            time.sleep(1)
            if len(self.alive_players) <= 1: continue

            now = time.time()
            dead_candidates = []
            alive_count = 0
            
            for p in list(self.alive_players):
                if p == self.my_ip: continue
                last = self.last_seen.get(p, now)
                if now - last > HEARTBEAT_TIMEOUT:
                    dead_candidates.append(p)
                else:
                    alive_count += 1
            
            total_others = len(self.alive_players) - 1
            
            if len(dead_candidates) == total_others and total_others > 0:
                if self.network_healthy:
                    print("\n[!] NETWORK UNSTABLE: Lost signal from EVERYONE.")
                    self.network_healthy = False
                    self.connection_lost_start = time.time()
                
                if self.connection_lost_start:
                    elapsed = time.time() - self.connection_lost_start
                    if elapsed > NETWORK_TIMEOUT_LIMIT:
                        print(f"\n[!!!] FATAL: Disconnected for {int(elapsed)}s. Terminating.")
                        os._exit(0)
                continue

            self.connection_lost_start = None

            if len(dead_candidates) > 0:
                if not self.network_healthy:
                    print("[!] NETWORK RESTORED.")
                    self.network_healthy = True

                for dead_ip in dead_candidates:
                    if dead_ip in self.alive_players:
                        print(f"\n[!!!] TIMEOUT: Player {dead_ip} stopped responding.")
                        self._send_udp_broadcast({'type': 'PLAYER_LEFT', 'dropout': dead_ip})
                        self._handle_player_left(dead_ip)

            if alive_count == total_others:
                self.network_healthy = True

    def _phase_discovery(self):
        print(f"\n--- PHASE 1: DISCOVERY ({DISCOVERY_TIME}s) ---")
        start_time = time.time()
        while time.time() - start_time < DISCOVERY_TIME:
            if self.game_running: break 
            self._send_udp_broadcast({'type': 'HELLO'})
            time.sleep(1)
        print("\n")

    def _phase_election(self):
        if self.game_running: return
        candidates = list(self.peers.keys()) + [self.my_ip]
        candidates.sort()
        highest_ip = candidates[-1]
        
        if self.my_ip == highest_ip:
            print("[!!!] I AM THE LEADER [!!!]")
            self.is_leader = True
            self._send_udp_broadcast({'type': 'VICTORY'})
        else:
            print(f"[---] Leader is {highest_ip}")
            self.is_leader = False

    def _phase_leader_lobby(self):
        print("\n" + "="*50 + "\n LOBBY CONTROL (LEADER)\n" + "="*50)
        while True:
            try:
                s = input(">> Enter Max Strikes allowed (e.g., 3): ")
                self.max_strikes = int(s)
                break
            except ValueError: pass

        while True:
            input(f">> Press ENTER to Start Game (Current Count: {len(self.peers) + 1}) ")
            current_list = list(self.peers.keys()) + [self.my_ip]
            current_list.sort()
            if len(current_list) < 2:
                print("Not enough players!")
                continue
            self.final_player_list = current_list
            break
        
        msg = {'type': 'GAME_START', 'players': self.final_player_list, 'max_strikes': self.max_strikes}
        for _ in range(5): 
            self._send_udp_broadcast(msg)
            time.sleep(0.1)

        for p in self.final_player_list: self.scores[p] = 0
        self.ui_queue.put({'type': 'MY_TURN_START', 'first_round': True})

    def _phase_follower_lobby(self):
        if self.game_running: return
        print("\n[Lobby] Waiting for Leader...")
        while True:
            self._send_udp_broadcast({'type': 'HELLO'})
            try:
                event = self.ui_queue.get(timeout=2)
                if event['type'] == 'GAME_START':
                    self.final_player_list = event['players']
                    self.max_strikes = event['max_strikes']
                    for p in self.final_player_list: self.scores[p] = 0
                    print(f"\n[!] GAME STARTED (Max Strikes: {self.max_strikes})")
                    return
                elif event['type'] == 'GAME_STATE':
                    if self.game_running: return
            except queue.Empty: pass

    def _connect_to_next_neighbor(self):
        if self.is_spectator: return
        try:
            my_idx = self.final_player_list.index(self.my_ip)
        except ValueError: return 

        total = len(self.final_player_list)
        target_ip = None
        for i in range(1, total):
            check_idx = (my_idx + i) % total
            candidate = self.final_player_list[check_idx]
            if candidate in self.alive_players:
                target_ip = candidate
                break
        
        if target_ip == self.my_ip and len(self.alive_players) > 1:
            return 
        
        if not target_ip:
            print(" [Network] No other players found.")
            return

        if self.neighbor_ip == target_ip and self.neighbor_sock: return
        if self.neighbor_sock:
            try: self.neighbor_sock.close()
            except: pass

        print(f" [Network] Connecting to Ring Neighbor: {target_ip}...", end="")
        while self.running:
            if not self.network_healthy: 
                time.sleep(1)
                continue
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((target_ip, TCP_PORT))
                s.settimeout(None)
                self.neighbor_sock = s
                self.neighbor_ip = target_ip
                print(" Success!")
                return
            except: 
                time.sleep(1)
                if target_ip not in self.alive_players: return

    # --- PHASE 5: GAME LOOP ---
    def _phase_game_loop(self):
        print("\n" + "*"*40)
        print(f"          GAME ON! {'(SPECTATOR)' if self.is_spectator else ''}         ")
        self._print_scoreboard()
        print("*"*40)

        while self.running:
            try:
                event = self.ui_queue.get()
                
                if event['type'] == 'MY_TURN_START':
                    if not self.is_spectator:
                        self.active_player_ip = self.my_ip 
                        self._do_turn(event.get('first_round', False), event.get('prev_claim', 0))
                
                elif event['type'] == 'TOKEN_RCV':
                    if not self.is_spectator:
                        self.active_player_ip = self.my_ip 
                        self._handle_incoming_token(event['token'])
                    
                elif event['type'] == 'ROUND_OVER':
                    self.turn_state = "IDLE"
                    self._handle_round_over(event)

                elif event['type'] == 'ANNOUNCE':
                    sender = event.get('sender', 'Unknown')
                    val = event.get('value', 0)
                    self.active_player_ip = sender 
                    if sender != self.my_ip:
                        print(f"\n [INFO] {sender} announced: {val}")

                # REMOVED: UDP ACK HANDLING IS NO LONGER NEEDED HERE

                elif event['type'] == 'TURN_CLAIM':
                    new_active = event.get('sender_ip')
                    self.active_player_ip = new_active
                    print(f"\n[!] TURN UPDATE: {new_active} claimed the turn (Crash Recovery).")
                
                elif event['type'] == 'PLAYER_LEFT':
                    self._handle_player_left(event['dropout'])

            except KeyboardInterrupt: break

    # ... [Keep _handle_player_left unchanged] ...
    def _handle_player_left(self, dropout_ip):
        try: self.alive_players.remove(dropout_ip)
        except ValueError: return 

        print(f"\n[!!!] GAME UPDATE: {dropout_ip} removed from ring.")
        self.scores[dropout_ip] = self.max_strikes 
        
        # Repair Neighbor Link
        if not self.is_spectator and self.neighbor_ip == dropout_ip:
            print(" [Repair] Neighbor lost. Finding new neighbor...")
            self.neighbor_sock = None
            self._connect_to_next_neighbor()
        
        # Check Win
        if len(self.alive_players) == 1:
            print(f"\n[GAME OVER] WINNER IS {self.alive_players[0]}!")
            self.running = False
            self._print_scoreboard()
            return

        # Turn Recovery
        if self.active_player_ip == dropout_ip:
            print(f"\n[!] ALERT: Active player {dropout_ip} dropped out!")
            try: dropout_idx = self.final_player_list.index(dropout_ip)
            except ValueError: return 

            total = len(self.final_player_list)
            successor = None
            for i in range(1, total):
                cand = self.final_player_list[(dropout_idx + i) % total]
                if cand in self.alive_players:
                    successor = cand
                    break
            
            if successor:
                print(f"    -> Successor calculated: {successor}")
                self.active_player_ip = successor
                if successor == self.my_ip:
                    print("    -> IT IS ME. CLAIMING TURN.")
                    self.turn_state = "IDLE"
                    time.sleep(1)
                    self._send_udp_broadcast({'type': 'TURN_CLAIM'})
                    self.ui_queue.put({'type': 'MY_TURN_START', 'first_round': True})
        
        self._print_scoreboard()
        
        # UI Refresh (Prompt Recovery)
        if self.active_player_ip == self.my_ip:
            print(f"\n[!] It is still your turn ({self.my_ip}).")
            if self.turn_state == "IDLE":
                print("    -> State mismatch detected. Restarting turn...")
                self.ui_queue.put({'type': 'MY_TURN_START', 'first_round': True})
            elif self.turn_state == "TRUST":
                print("    -> Waiting for input: >> Trust? (y/n): ")
            elif self.turn_state == "ANNOUNCE":
                print("    -> Waiting for input: >> Announce: ")

    def _handle_incoming_token(self, token):
        # REMOVED: UDP ACK SENDING
        
        token_sig = token['security']['hash']
        if self.last_processed_token_sig == token_sig: return
        self.last_processed_token_sig = token_sig

        prev_claim = token['announced']
        print(f"\n[YOUR TURN] Previous Claim: {prev_claim}")
        
        self.turn_state = "TRUST"

        if prev_claim == 21:
            print("!"*40 + "\n DANGER: MÄXCHEN (21)! [Y]ield or [C]heck?\n" + "!"*40)
            while True:
                choice = input(">> (y/c): ").lower()
                if choice == 'y':
                    msg = {'type': 'ROUND_OVER', 'loser': self.my_ip, 
                           'real_value': 'Hidden', 'points': 1, 'reason': 'Yielded (21)'}
                    self._send_udp_broadcast(msg)
                    return
                elif choice == 'c':
                    self._resolve_bluff_locally(token, is_maexchen_round=True)
                    return
        else:
            while True:
                choice = input(">> Trust? (y/n): ").lower()
                if choice == 'n':
                    self._resolve_bluff_locally(token, is_maexchen_round=False)
                    return
                elif choice == 'y':
                    break
            self._do_turn(first_round=False, prev_claim=prev_claim)

    # ... [Keep _resolve_bluff_locally, _handle_round_over, _do_turn unchanged] ...
    def _resolve_bluff_locally(self, token, is_maexchen_round):
        self.turn_state = "IDLE"
        real = token['security']['hidden_real']
        claim = token['announced']
        prev_player_ip = token.get('sender_ip', 'unknown')
        
        if not self.game_engine.verify_hash(token):
             print("[!] SECURITY ALERT: Token Tampered.")
             loser = prev_player_ip
        elif real != claim:
            print(f">> THEY LIED (Real: {real} vs Claim: {claim}).")
            loser = prev_player_ip
        else:
            print(f">> THEY TOLD TRUTH (Real: {real}).")
            loser = self.my_ip
        
        points = 2 if is_maexchen_round else 1
        self._send_udp_broadcast({'type': 'ROUND_OVER', 'loser': loser,
                                  'real_value': real, 'points': points, 'reason': 'Bluff Called'})

    def _handle_round_over(self, msg):
        self.turn_state = "IDLE"
        loser = msg['loser']
        pts = msg.get('points', 1)
        self.active_player_ip = loser

        print(f"\n[ROUND OVER] Loser: {loser} (+{pts}) | Real: {msg['real_value']}")
        if loser in self.scores: self.scores[loser] += pts
        
        is_eliminated = self.scores.get(loser, 0) >= self.max_strikes
        if is_eliminated and loser in self.alive_players:
            print(f"[!!!] {loser} ELIMINATED.")
            try: self.alive_players.remove(loser)
            except: pass
            
            if loser == self.my_ip:
                print(">> YOU ARE OUT. SPECTATOR MODE.")
                self.is_spectator = True
                if self.neighbor_sock: self.neighbor_sock.close()
            self._connect_to_next_neighbor()

        self._print_scoreboard()
        if len(self.alive_players) == 1:
            print(f"\n[GAME OVER] WINNER IS {self.alive_players[0]}!")
            self.running = False
            return

        starter = loser
        if is_eliminated:
            try: loser_idx = self.final_player_list.index(loser)
            except ValueError: return
            total = len(self.final_player_list)
            for i in range(1, total):
                cand = self.final_player_list[(loser_idx + i) % total]
                if cand in self.alive_players:
                    starter = cand
                    break
            self.active_player_ip = starter

        if self.my_ip == starter:
            print("\n[!] Your turn to start.")
            time.sleep(2)
            self.ui_queue.put({'type': 'MY_TURN_START', 'first_round': True})
        else:
            print(f"\n[!] Waiting for {starter}...")

    def _do_turn(self, first_round, prev_claim):
        self.turn_state = "ANNOUNCE"
        if not first_round:
            input(">> Press ENTER to roll dice...")
        
        real_val = self.game_engine.roll_dice()
        print(f"   [HIDDEN ROLL] {real_val}")
        
        final_claim = 0
        while True:
            try:
                user_input = input(f">> Announce (> {prev_claim}): ")
                claim = int(user_input)
                is_valid, err = self.game_engine.validate_announcement(claim, prev_claim)
                if is_valid:
                    final_claim = claim
                    break
                else:
                    print(f"   [!] {err}")
            except ValueError: pass

        self._send_udp_broadcast({'type': 'ANNOUNCE', 'value': final_claim, 'sender': self.my_ip})
        token = self.game_engine.secure_cup(real_val, final_claim)
        
        self.turn_state = "IDLE"
        
        retry_count = 0
        MAX_RETRIES = 3
        
        while True:
            success = self._send_tcp_token_with_ack(token)
            if success:
                break
            else:
                retry_count += 1
                if retry_count >= MAX_RETRIES:
                    print(f"\n[!!!] NEIGHBOR FAILED TO ACK {MAX_RETRIES} TIMES. ELIMINATING THEM.")
                    
                    dead_neighbor = self.neighbor_ip
                    self._send_udp_broadcast({'type': 'PLAYER_LEFT', 'dropout': dead_neighbor})
                    self._handle_player_left(dead_neighbor)
                    
                    if len(self.alive_players) <= 1: break
                    
                    print(" [Retry] Retrying send to NEW neighbor...")
                    retry_count = 0 
                    continue
                
                print(f"[!] Handover failed (Attempt {retry_count}/{MAX_RETRIES}). Retrying in 2s...")
                time.sleep(2)

    # --- UPDATED TCP SENDER (SYNCHRONOUS ACK) ---
    def _send_tcp_token_with_ack(self, token):
        while not self.network_healthy:
            print(" [Wait] Connection unstable. Retrying in 2s...")
            time.sleep(2)

        if not self.neighbor_sock: self._connect_to_next_neighbor()
        if not self.neighbor_sock: return False

        token['sender_ip'] = self.my_ip
        msg = json.dumps({'type': 'TOKEN', 'payload': token}) + "\n"
        
        try:
            # 1. Send the Token
            self.neighbor_sock.sendall(msg.encode())
            print(f">> Cup passed to {self.neighbor_ip}. Waiting for confirmation...")
            
            # 2. Wait immediately for ACK on the same socket (TCP reliability)
            # Use a short timeout so we don't hang forever if neighbor crashes mid-receive
            self.neighbor_sock.settimeout(3.0) 
            response_bytes = self.neighbor_sock.recv(1024)
            self.neighbor_sock.settimeout(None) # Reset timeout
            
            if not response_bytes:
                print(f">> Error: Socket closed by {self.neighbor_ip}.")
                self.neighbor_sock = None
                return False

            response = json.loads(response_bytes.decode())
            if response.get('type') == 'ACK':
                print(f">> Handover confirmed!")
                return True
            else:
                print(f">> Unexpected response: {response}")
                return False

        except Exception as e:
            print(f"[!] Send failed: {e}")
            self.neighbor_sock = None
            return False
            
    def _print_scoreboard(self):
        print("\n--- SCOREBOARD ---")
        for p in self.final_player_list:
            score = self.scores.get(p, 0)
            status = "ALIVE" if p in self.alive_players else "DEAD"
            marker = " (YOU)" if p == self.my_ip else ""
            print(f" {p}{marker}: {score}/{self.max_strikes} [{status}]")
        print("------------------")

    # --- NETWORK HELPERS ---
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

    # --- UPDATED TCP HANDLER (SYNCHRONOUS ACK) ---
    def _handle_tcp_stream(self, conn):
        with conn:
            f = conn.makefile('r', encoding='utf-8')
            for line in f:
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    if data['type'] == 'TOKEN':
                        # 1. Reject if Spectator
                        if self.is_spectator:
                             # Optional: Send error ACK? For now just ignore/close.
                             return 

                        # 2. SEND ACK IMMEDIATELY VIA TCP
                        # This ensures the sender knows we got it before we process logic
                        ack_msg = json.dumps({'type': 'ACK'})
                        conn.sendall(ack_msg.encode())
                        
                        # 3. Queue for Game Logic
                        self.ui_queue.put({'type': 'TOKEN_RCV', 'token': data['payload']})
                except: pass

    def _listen_udp(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', BROADCAST_PORT))
        while self.running:
            try:
                data, addr = s.recvfrom(BUF_SIZE)
                msg = json.loads(data.decode())
                if msg.get('group') != self.group_hash: continue
                
                sender_ip = msg.get('sender_ip', addr[0])
                self.last_seen[sender_ip] = time.time()

                if msg['type'] == 'HELLO':
                    if sender_ip != self.my_ip:
                         self.peers[sender_ip] = time.time()
                         if self.game_running and not self.is_spectator:
                             state_msg = {
                                 'type': 'GAME_STATE',
                                 'players': self.final_player_list,
                                 'alive': self.alive_players,
                                 'scores': self.scores,
                                 'max_strikes': self.max_strikes,
                                 'active': self.active_player_ip
                             }
                             self._send_udp_broadcast(state_msg)

                elif msg['type'] == 'GAME_STATE':
                    if not self.game_running:
                        self.final_player_list = msg['players']
                        self.alive_players = msg['alive']
                        self.scores = msg['scores']
                        self.max_strikes = msg['max_strikes']
                        self.active_player_ip = msg.get('active')
                        self.game_running = True
                        self.is_spectator = True
                        self.ui_queue.put(msg)


                if msg['type'] in ['GAME_START', 'ANNOUNCE', 
'ROUND_OVER', 'PLAYER_LEFT', 'TURN_PASS', 'TURN_CLAIM']:
                    self.ui_queue.put(msg)
            except Exception: pass

    def _send_udp_broadcast(self, msg):
        msg.update({'group': self.group_hash, 'sender_ip': self.my_ip})
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(json.dumps(msg).encode(), ('<broadcast>', BROADCAST_PORT))
        except: pass

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('10.255.255.255', 1))
            return s.getsockname()[0]
        except: return '127.0.0.1'