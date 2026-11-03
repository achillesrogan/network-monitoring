# Read the network_devices.csv file and print the list of devices.

import netlib

devices = netlib.read_devices()

print("Network Devices")
print("---------------")
for device in devices:
    print(device["Device ID"] + "  " + device["Device Name"].ljust(8) +
          device["Device Address"].ljust(16) + device["OS"])

print("---------------")
print("Total devices: " + str(len(devices)))
