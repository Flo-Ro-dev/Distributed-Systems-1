#!/bin/bash

# Check for root
if [ "$EUID" -ne 0 ]; then 
  echo "Please run as root"
  exit
fi

echo "Creating bridge br_ds..."
ip link add name br_ds type bridge
ip link set br_ds up
ip addr add 10.0.0.254/24 dev br_ds

# Create 3 Clients
for i in 1 2 3
do
    NS="client$i"
    VETH="veth$i"
    VETH_BR="veth${i}_br"
    IP="10.0.0.$i"

    echo "Setting up $NS with IP $IP..."

    # 1. Create Namespace
    ip netns add $NS

    # 2. Create veth pair
    ip link add $VETH type veth peer name $VETH_BR

    # 3. Move one end to namespace, keep other on host
    ip link set $VETH netns $NS
    ip link set $VETH_BR master br_ds

    # 4. Bring up host side interface
    ip link set $VETH_BR up

    # 5. Configure namespace side (IP, Loopback, Interface Up)
    ip netns exec $NS ip addr add $IP/24 dev $VETH
    ip netns exec $NS ip link set $VETH up
    ip netns exec $NS ip link set lo up
    
    # Optional: Add default route via bridge (if you want them to reach the host)
    ip netns exec $NS ip route add default via 10.0.0.254
done

echo "Network initialized."
echo "Verify with: ip netns list"
