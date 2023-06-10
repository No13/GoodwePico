"""Main module to run programm
"""
# pylint: disable=W0702,W0718,E0401,W0621
from time import sleep
import json
import socket
import select
import machine
import network
from machine import Pin, UART, Timer
from goodwecomm import GoodweComm

def write_config(config):
    """Write config.json with values
    """
    with open('config.json','w', encoding='utf-8') as configfile:
        json.dump(config, configfile)

def connect(ssid, psk):
    """Connect to WLAN
    """
    if ssid != "":
        wlan = network.WLAN(network.STA_IF)
        wlan.config(hostname='Goodwe-WIFI')
        wlan.active(True)
        wlan.connect(ssid,psk)
        retries = 10
        # When not connected after 10 tries it will probably not happen
        while wlan.isconnected() is False:
            print('Waiting for connection...')
            sleep(1)
            retries -= 1
            if retries == 0:
                machine.reset()
        print(wlan.ifconfig())
        return wlan
    wlan = network.WLAN(network.AP_IF)
    wlan.config(essid='GoodweWIFI', password=psk)
    print(f"AP Active with password: {psk}")
    wlan.active(True)
    return wlan

def main_loop(_):
    """Run listen functions within the timer
    """
    goodwe.listen_uart()
    goodwe.listen_tcp()
    goodwe.listen_udp()
    webserver()

def webserver():
    """Wait 50msec for connection, handle clients
    """
    res = poller.poll(50)
    if res:
        try:
            conn, addr = s.accept()
            print(f'Got a connection from {str(addr)}')
            request = conn.recv(1024)
            request = str(request)
            #print('Content = %s' % request)
            content = htmlpage
            param = request.find('/config')
            if param > 0:
                content = '<html><head></head><body>'
                content += '<a href="/reset/">Reset PI</a><br />'
                content += '<a href="/pvstat/">Get PV stats</a><br />'
                params = request[param:]
                params = params[:params.find(' ')]
                if 'ssid' in params:
                    ssid = params[params.find('ssid=')+5:params.find('&')]
                    print(f'SSID -{ssid}-')
                    psk = params[params.find('psk=')+4:params.find(';')]
                    print(f'PSK -{psk}-')
                    config['ssid'] = ssid
                    config['psk'] = psk
                    write_config(config)
                    content += "<h3>SSID info saved!</h3>"
            if request.find('/reset/') > 0:
                machine.reset()
            if request.find('/pvstat/') > 0:
                content = json.dumps(goodwe.get_pv_stats())

            conn.send('HTTP/1.1 200 OK\n')
            if 'html' in content:
                conn.send('Content-Type: text/html\n')
            else:
                conn.send('Content-Type: application/json\n')
                conn.send('Access-Control-Allow-Origin: *\n')
            conn.send('Connection: close\n\n')
            conn.sendall(f'{content}')
            conn.close()
        except Exception as web_err:
            print(f'Died {web_err}')

# Load config for wifi credentials and goodwe communication host
try:
    with open('config.json', 'r', encoding='utf-8') as configfile:
        config = json.load(configfile)
except:
    config = {
        'psk': 'goodwewifi',
        'ssid': '',
        'goodwe_host': 'tcp.goodwe-power.com',
        'goodwe_port': 20001,
        }
    write_config(config)

with open('index.html', 'r', encoding='utf-8') as indexhtml:
    htmlpage = indexhtml.read()
# Create UART instance, needed for communication with inverter
uart = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5))
uart.init(bits=8, parity=None, stop=1)

# Wifi object is used in communicating RSSI values to inverter
wlan = connect(config['ssid'], config['psk'])
goodwe = GoodweComm(uart, wlan, config)

# Start webserver and use poll for handling connections
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 80))
s.listen(5)
print('Serving...')
poller = select.poll()
poller.register(s, select.POLLIN)

# This fires the main loop every 300 msec
loop_timer = Timer(
    mode=Timer.PERIODIC,
    period=300,
    callback=main_loop)
