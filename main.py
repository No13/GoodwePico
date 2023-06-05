"""Main module to run programm
"""
# pylint: disable=E0401
from time import sleep
import network
import machine
import json
from machine import Pin, UART, Timer
from goodwecomm import GoodweComm
import socket

def write_config(config):
    with open('config.json','w') as configfile:
        json.dump(config, configfile)
    
try:
    with open('config.json','r') as configfile:
        config = json.load(configfile)
except:
    config = {
        'psk': 'goodwewifi',
        'ssid': '',
        'goodwe_host': 'tcp.goodwe-power.com',
        'goodwe_port': 20001,
        }
    write_config(config)

uart = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5))
uart.init(bits=8, parity=None, stop=1)

def connect(ssid, psk):
    """Connect to WLAN
    """
    if ssid is not "":
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

wlan = connect(config['ssid'], config['psk'])
goodwe = GoodweComm(uart, wlan, config)

def main_loop(_):
    """Run listen functions within the timer
    """
    goodwe.listen_uart()
    goodwe.listen_tcp()
    goodwe.listen_udp()

loop_timer = Timer(
    mode=Timer.PERIODIC,
    period=300,
    callback=main_loop)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))
s.listen(5)
print('Serving...')
while True:
    try:
        conn, addr = s.accept()
        print('Got a connection from %s' % str(addr))
        request = conn.recv(1024)
        request = str(request)
        #print('Content = %s' % request)
        param = request.find('/config/?')
        content = '<html><head></head><body>'
        content += '<a href="/reset/">Reset PI</a><br />'
        content += '<a href="/pvstat/">Get PV stats</a><br />'

        if param > 0:
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
            content = f'{goodwe.get_pv_stats()}'

        conn.send('HTTP/1.1 200 OK\n')
        if 'html' in content:
            conn.send('Content-Type: text/html\n')
        else:
            conn.send('Content-Type: text/json\n')
        conn.send('Connection: close\n\n')
        conn.sendall(f'{content}')
        conn.close()
    except KeyboardInterrupt:
        s.close()
        break;
    except Exception as web_err:
        print(f'Died {web_err}')
