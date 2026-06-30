import logging
import socket

class LogstashTcpHandler(logging.Handler):
    def __init__(self, host: str, port: int = 5000):
        super().__init__()
        if ":" in host:
            self.host, port_str = host.split(":", 1)
            try:
                self.port = int(port_str)
            except ValueError:
                self.port = port
        else:
            self.host = host
            self.port = port

    def emit(self, record):
        try:
            message = self.format(record) + "\n"
            with socket.create_connection((self.host, self.port), timeout=5.0) as sock:
                sock.sendall(message.encode("utf-8"))
        except Exception:
            self.handleError(record)
