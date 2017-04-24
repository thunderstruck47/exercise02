__version__ = "0.0.0"

import socket
import os

# The following need to be set in server.conf
HOST = ""
PORT = 80
REQ_BUFFSIZE = 4096

def test():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST,PORT))
    s.listen(1)
    print "* Serving at http://127.0.0.1:{0}/ (Press CTRL+C to quit)".format(PORT)
    while True:
        conn, addr = s.accept()
        data = conn.recv(REQ_BUFFSIZE)
        http_response = b"HTTP/1.1 200 OK\r\n\r\nHello, World!\r\n"
        conn.sendall(http_response)
        conn.close()

if __name__ == "__main__":
    test()
    print "Bye"
