import socket
import threading
import time
import argparse
import sys

def get_ip_address():
    """Helper to find the local IP address for filtering own messages."""
    try:
        # Connect to a dummy external IP to determine which interface is active
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def listen_task(sock, my_ip, buffer_size=1024):
    """Listens for incoming UDP packets."""
    print(f"[*] Listening on {sock.getsockname()} (My IP: {my_ip})")
    
    while True:
        try:
            data, addr = sock.recvfrom(buffer_size)
            sender_ip, sender_port = addr
            
            # Optional: Ignore messages from self
            if sender_ip == my_ip:
                continue

            print(f"[Received] from {sender_ip}:{sender_port} -> {data.decode('utf-8')}")
            
        except OSError:
            break  # Socket closed
        except Exception as e:
            print(f"[Error] Listener error: {e}")

def send_task(sock, target_ip, target_port, message, interval):
    """Sends broadcast packets."""
    print(f"[*] Broadcasting to {target_ip}:{target_port} every {interval}s")
    while True:
        try:
            sock.sendto(message.encode('utf-8'), (target_ip, target_port))
            time.sleep(interval)
        except Exception as e:
            print(f"[Error] Sender error: {e}")
            time.sleep(1)

def main():
    parser = argparse.ArgumentParser(description="UDP Broadcast Peer")
    
    # Arguments
    parser.add_argument("--bind-ip", default="0.0.0.0", help="IP to listen on")
    parser.add_argument("--bind-port", type=int, required=True, help="Port to listen on")
    parser.add_argument("--target-ip", default="255.255.255.255", help="Broadcast IP target")
    parser.add_argument("--target-port", type=int, required=True, help="Target Port to send to")
    parser.add_argument("--message", default="Hello Broadcast!", help="Message content")
    parser.add_argument("--interval", type=float, default=2.0, help="Send interval in seconds")
    
    args = parser.parse_args()

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # IMPORTANT: Enable Broadcast
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    # Allow reusing the address (helps if restarting script quickly)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind((args.bind_ip, args.bind_port))
    except Exception as e:
        print(f"[Fatal] Could not bind to {args.bind_ip}:{args.bind_port} - {e}")
        sys.exit(1)

    # Get local IP to filter own messages in the listener
    my_ip = get_ip_address()

    # Start the listener thread
    listener = threading.Thread(target=listen_task, args=(sock, my_ip), daemon=True)
    listener.start()

    # Start the sender loop
    try:
        send_task(sock, args.target_ip, args.target_port, args.message, args.interval)
    except KeyboardInterrupt:
        print("\n[*] Stopping...")
        sock.close()

if __name__ == "__main__":
    main()
