# Distributed-Systems-1
## Game rules: Mäxchen
Mäxchen is a bluffing game where players secretly roll two dice and announce a result that must be higher than the previous one, by telling the truth or lying.
The next player may either believe the announcement and continue rolling the two dice or doubt it and reveal the dice. When revealing: if the announcement was true
the doubter (current player) gets a strike, if it was false, the announcer (previous player) gets a strike. If a player receives a defined number of strikes, they are 
eliminated. The game runs until only one player is left. This is the ranking of possible rolls:

```
31, 32,
41, 42, 43,
51, 52, 53, 54,
61, 62, 63, 64, 65,
11, 22, 33, 44, 55, 66,
21  # Mäxchen
```
The higher die is always placed first. Doublets are more worth. The Mäxchen (21) is the highest score.
When a Mäxchen is doubted wrong, the player usually receives a higher amount of strikes. Since rolling higher is not possible,
the last player can also believe the Mäxchen and receive a smaller amount of strikes.

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

