"""
  # Abgabe 03.02 (Dienstag)

  main.py
  config.py

  game/
    player.py          # Represents a player and his attributes
    rules.py           # Static methods for game rules
    ui.py              # Front-End
    dice_game.py       # Game-loop

  net/
    messages.py        # Message-Format (JSON), encode/decode
    udp_discovery.py   # Broadcast DISCOVER + OFFER Listener
    transport.py       # Send/recv, retries/acks (optional)
    tcp_join.py        # (optional) Join per TCP statt UDP

  core/
    state.py           # Zustandsmodell: Lobby / Round / Players
    node.py            # GameNode: verbindet alles (Netz + Core)
    voting.py          # Propose/YesNo/Commit

  util/
    ids.py             # UUID helpers
    clock.py           # timeouts/backoff
    log.py
"""

import socket
from net import udp_discover_listener, udp_discover_sender 

if __name__ == '__main__':
 # Broadcast address and port (example for a /24 network)
 BROADCAST_IP = "255.255.255.255"
 BROADCAST_PORT = 5973
 # Local host information
 my_host = socket.gethostname()
 my_ip = socket.gethostbyname(my_host)
 # Compose broadcast announcement
 announcement = my_ip + " sent a broadcast message"
 # Send the broadcast announcement
 udp_discover_sender.broadcast(BROADCAST_IP, BROADCAST_PORT, announcement)