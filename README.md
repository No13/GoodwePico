# Intro
The reason for this project... I like my Wifi to be clean. Every Goodwe inverter adding an accesspoint to my environment is not part of that :)
To fix this I created a bit of Python code to 'simulate' the original Wifi module.
It's not a particularly good kind of simulation but it works for now.

# Notice on wiring
Please note that the USB3.0 GND and +5V are swapped. Three of the 5 USB3 pins are used for TX/RX to the Pico W (To GP4 and GP5 for UART1)

# How to replicate
Buy a Pico W module, solder an old USB3 connector to it (make sure the USB3 cable is shielded. You need this for certain models of inverter as it is the only GND connection)
Drag & drop a recent micropython version onto the flash (I use 1.20) and copy the two .py files using Thonny or any other tool to transfer code.

# First boot
When you do not supply a config.json, the default will create this file and start an accesspoint on GoodweWIFI using psk 'goodwewifi'.
Fill your own config.json with the appropriate stuff to connect to your own network

# What now?
The module should connect to tcp.goodwe-power.com on port 20001 to send information back to the SEMS portal (I do not use this).
On port 8899 (udp) it will listen for the magic UDP packet (modbus?) to reply with the actual status
On port 80 there is a *very* limited webserver from which you can reset the module or try to read the status.

# TODO?
I think setting values will not work over UDP (untested) and discovery (port 48899) is not implemented.
