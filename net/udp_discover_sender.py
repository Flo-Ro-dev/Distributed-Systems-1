import socket

def broadcast(ip, port, broadcast_announcement):
 # Create a UDP socket
 broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
 # Enable permission to send to broadcast addresses
 broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
 # Send the broadcast announcement
 broadcast_socket.sendto(str.encode(broadcast_announcement), (ip, port))
