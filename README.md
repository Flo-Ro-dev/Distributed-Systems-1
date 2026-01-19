# Distributed-Systems-1

## Broadcasting
At the moment only broadcasting messages from Client to other Clients is possible.

### Setup network
This creates 3 seperate network namespaces using the `ip` tool. The network namespaces are isolated from each other and connected via a bridge, `br_ds` that lives in the hosts namespace.
```
sudo bash init_network.sh
```
The namespaces have the names `client1` (`10.0.0.2`), `client2` (`10.0.0.3`) and `client3` (`10.0.0.4`).
// TODO optimize IP-range because there is no Gateway.

### Run the script
Be aware the script at the moment is fully vibe-coded with Gemini-3 Pro. Open three different terminals.

*Terminal 1*
```
sudo ip netns exec client1 python3 src/udp_test.py \
  --bind-port 5000 \
  --target-ip 10.0.0.255 \
  --target-port 5000 \
  --message "This is Client 1"
```

*Terminal 2*
```
sudo ip netns exec client2 python3 src/udp_test.py \
  --bind-port 5000 \
  --target-ip 10.0.0.255 \
  --target-port 5000 \
  --message "This is Client 2"
```

*Terminal 3*
```
sudo ip netns exec client3 python3 test/udp_test.py \
  --bind-port 5000 \
  --target-ip 10.0.0.255 \
  --target-port 5000 \
  --message "This is Client 3"
```

This sends all messages to the broadcast address of the subnet. It would also be possible to port this script to layer 2 and use MAC-addresses but this is not discussed here.

### Cleanup
To remove the namespaces reboot you machine or run:
```
sudo bash cleanup_network.sh
```

## Python Hints
It may makes sense to run the script in a Python virtual environment. The environment is precreated in this repository to activate it run:
```
source .venv/bin/activate
```
