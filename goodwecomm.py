"""Goodwe communication class
"""
import time
import socket
from log import Logger

#pylint: disable=W0702,W0511,W0718
class GoodweComm:
    """Class for Goodwe XS communication based on AT commands
    """
    at_mode = True
    udp_conn = None
    udp_socket = None
    tcp_socket = None

    def __init__(self, uart, wlan, config):
        """Create instance and set UART
        """
        self.uart = uart
        self.wlan = wlan
        self.config = config
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        self.udp_socket.bind(('',8899))
        self.udp_socket.settimeout(0)
        self.log = Logger(config['syslog_host'], config['syslog_port'])

    def listen_udp(self):
        """Check for new UDP packets and parse it
        This function should be run regularly
        """
        try:
            bytes_on_udp, peer_addr = self.udp_socket.recvfrom(1024)
            self.udp_conn = peer_addr
            self.send_uart(bytes_on_udp)
        except:
            pass

    def listen_tcp(self):
        """Listen to replies from goodwe and send to UART
        """
        if self.tcp_socket:
            # Ignore all errors, handle only when sending data
            try:
                recv_data = self.tcp_socket.recv(2048)
                if len(recv_data) > 10:
                    self.uart.write(recv_data)
                    self.log.send(f"TCP reply: {recv_data}")
            except:
                pass

    def listen_uart(self):
        """Check for new serial data and parse it
        This function should be run regularly
        """
        # If data is actively being received; please wait a bit for it to settle
        bytes_on_serial = self.uart.any()
        bytes_data = bytearray()
        timeout = time.time() + 5
        while self.uart.any() != 0 and time.time() < timeout:
            time.sleep(0.05)
            for bit in self.uart.read(bytes_on_serial):
                bytes_data.append(bit)

        self.__parse__(bytes_data)

    def __parse__(self, bytes_data):
        """Parse incoming data
        """
        # Sanity checks
        data_len = len(bytes_data)

        # Case '+++'
        if (data_len == 3 and
            bytes_data[0] == 0x2b and
            bytes_data[2] == 0x2b):
            self.at_mode = True
            self.send_uart('a')
            return

        # Case 'a'
        if data_len == 1 and bytes_data[0] == 0x61:
            # Got 'a'
            if self.at_mode:
                self.send_uart('+ok\r\n\r\n')
            return

        # Case 'AT+'
        if (data_len > 3 and
            bytes_data[0] == 0x41 and
            bytes_data[1] == 0x54 and
            bytes_data[2] == 0x2b):
            response = self.__parse_at__(bytes_data)
            if response:
                self.send_uart(response)
            return

        # Case 'POSTGW'
        if (data_len > 6 and
            bytes_data[0:6] == b'POSTGW'):
            if self.config['call_home']:
                self.send_tcp(bytes_data)
            return
        # Case other
        if data_len > 3:
            self.send_udp(bytes_data)

    def send_uart(self, data):
        """Send data on UART
        """
        self.log.send(f'uart {data}')
        self.uart.write(data)

    def send_tcp(self, data):
        """Send data on new TCP link
        """
        self.log.send(f'TGP send {len(data)} {data}')
        if not self.tcp_socket:
            self.tcp_socket = socket.socket()
            self.tcp_socket.settimeout(0)
            self.tcp_socket.connect(
                socket.getaddrinfo(
                    self.config['goodwe_host'],
                    self.config['goodwe_port'],
                    0, socket.SOCK_STREAM)[0][-1])
        try:
            self.tcp_socket.send(data)

        except Exception as tcp_error:
            try:
                self.tcp_socket.close()
            finally:
                self.tcp_socket = None
            self.log.send(f"TCP error {tcp_error}")

    def send_udp(self, data):
        """Send data on existing UDP connection
        """
        if self.udp_conn:
            self.udp_socket.sendto(data, self.udp_conn)
        # print(f'udp {len(data)} {data}')

    def __parse_at__(self, data):
        """Parse and handle AT data
        """
        at_string = data.decode('utf-8')
        at_cmd = at_string[3:].strip()
        param = None
        if '=' in at_cmd:
            end = at_cmd.index('=')
            param = at_cmd[(end+1):]
            at_cmd = at_cmd[:end]

        dbm = self.wlan.status('rssi')

        wlan_quality = min(max(2 * (dbm+100), 0), 100)

        ssid = self.wlan.config('ssid')

        mac = ''
        for bit in self.wlan.config('mac'):
            part = f'{bit:#04x}'
            mac += part[2:]
        gwport = self.config["goodwe_port"]
        gwhost = self.config["goodwe_host"]
        # TODO: If new URL is sent via NETP we need to update config/script
        replies = {
            'APPVER': 'AT+APPVER\r\n\r+ok=v2.0.0.0\r\n\r\n',
            'ENTM': 'AT+ENTM\r\n\r+ok\r\n\r\n',
            'NETP': f'AT+NETP\r\n+ok=TCP,Client,{gwport},{gwhost}\r\n\r\n',
            'PLANG': 'AT+PLANG\r\n\r+ok=EN\r\n\r\n',
            'TCPTO': f'AT+TCPTO={param}\r\n\r+ok\r\n\r\n',
            'WAP': 'AT+WAP\r\n\r+ok=11BGN,Solar-WiFi,AUTO\r\n\r\n',
            'WMODE': f'AT+WMODE={param}\r\n\r+ok\r\n\r\n',
            'WSLK': f'AT+WSLK\r\n\r+ok={ssid}(aa:bb:cc:dd:ee:ff)\r\n\r\n',
            'WSLQ': f'AT+WSLQ\r\n\r+ok=Normal, {wlan_quality}%\r\n\r\n',
            'WSMAC': f'AT+WSMAC\r\n\r+ok={mac}\r\n\r\n',
            'WSSSID': f'AT+WSSSID\r\n\r+ok={ssid}\r\n\r\n',
        }

        if at_cmd in replies:
            return replies[at_cmd]
        return None

    def crc16(self, data: bytes):
        '''
        CRC-16-ModBus Algorithm
        '''
        data = bytearray(data)
        poly = 0xA001
        crc = 0xFFFF
        for data_byte in data:
            crc ^= (0xFF & data_byte)
            for _ in range(0, 8):
                if crc & 0x0001:
                    crc = ((crc >> 1) & 0xFFFF) ^ poly
                else:
                    crc = (crc >> 1) & 0xFFFF
        return crc

    def get_int(self, in_bytes):
        '''
        Convert powerrange of bytes to integer
        '''
        if isinstance(in_bytes, int):
            return in_bytes
        return int.from_bytes(in_bytes[:len(in_bytes)], 'big')


    def get_pv_stats(self):
        """Send modbus command to inverter and output reply
        """
        crc_data = 1
        crc_calc = 2
        tries = 5
        while (crc_data != crc_calc) and (tries > 0):
            timestamp = time.time()+2
            self.send_uart(b'\x7f\x03u\x94\x00I\xd5\xc2')
            bytes_data = bytearray()
            while (self.uart.any() == 0) and time.time() < timestamp:
                time.sleep(0.1)
            while self.uart.any() != 0 and time.time() < timestamp:
                time.sleep(0.05)
                for bit in self.uart.read(self.uart.any()):
                    bytes_data.append(bit)
            self.log.send(f'Data is binnen: #{tries} {bytes_data}')
            crc_data = bytes_data[-1:].hex()+bytes_data[-2:-1].hex()
            crc_calc = hex(self.crc16(bytes_data[2:-2]))[2:]
            tries -= 1
        #return f'{len(bytes_data)} {crc_data} {crc_calc}'
        if crc_data == crc_calc:
            self.log.send('Success decoding data')
            inverter_data = {
                'error': 'no error',
                'vpv1': round(self.get_int(bytes_data[11:13])*0.1, 2),
                'ipv1': round(self.get_int(bytes_data[13:15])*0.1, 2),
                'vpv2': round(self.get_int(bytes_data[15:17])*0.1, 2),
                'ipv2': round(self.get_int(bytes_data[17:19])*0.1, 2),
                'vac': round(self.get_int(bytes_data[41:43])*0.1, 2),
                'iac': round(self.get_int(bytes_data[47:49])*0.1, 2),
                'fac': round(self.get_int(bytes_data[53:55])*0.01, 2),
                'eday': round(self.get_int(bytes_data[93:95])*0.1, 2),
                'etot': round(self.get_int(bytes_data[95:99])*0.1, 2),
                'rssi': self.get_int(bytes_data[149:151]),
                'hours': self.get_int(bytes_data[101:103]),
                'temp': round(self.get_int(bytes_data[87:89])*0.1, 2),
                'power': self.get_int(bytes_data[61:63]),
                'status': self.get_int(bytes_data[63:65]),
                'timestamp': time.mktime((2000+self.get_int(bytes_data[5]),
                                            self.get_int(bytes_data[6]),
                                            self.get_int(bytes_data[7]),
                                            self.get_int(bytes_data[8]),
                                            self.get_int(bytes_data[9]),
                                            self.get_int(bytes_data[10]), -1, -1, -1))}
            return inverter_data
        return {'error': 'no data'}
