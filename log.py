import socket

class Logger:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, msg):
        """Send data on existing UDP connection
        """
        self.sock.sendto(msg.encode('utf-8'), (self.host, self.port))
