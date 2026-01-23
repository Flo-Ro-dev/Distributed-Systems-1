#!/bin/bash

if [ "$EUID" -ne 0 ]; then 
  echo "Please run as root"
  exit
fi

echo "Cleaning up network..."

# Remove bridge (this automatically deletes attached veth interfaces on the host side)
ip link delete br_ds

# Remove namespaces (this automatically deletes the veth interfaces inside them)
for i in 1 2 3
do
    ip netns del client$i 2>/dev/null
    echo "Removed client$i"
done

echo "Cleanup complete."
