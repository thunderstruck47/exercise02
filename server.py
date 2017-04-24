__version__ = "0.0.0"

import socket
import os

# The following need to be set in server.conf
HOST = ""
PORT = 80
REQ_BUFFSIZE = 4096
BASE_DIR = "www"
INDEX_FILE = "\index.html"
HTTP_200 = b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
HTTP_404 = b"HTTP/1.1 404 Not Found\r\n\r\n"
HTTP_403 = b"HTTP/1.1 403 Forbidden\r\n\r\n"

def test():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST,PORT))
    s.listen(1)
    print "* Serving at http://127.0.0.1:{0}/ (Press CTRL+C to quit)".format(PORT)
    while True:
        conn, addr = s.accept()
        http_request = conn.recv(REQ_BUFFSIZE)
        http_path = http_request.split("\n",1)[0].split()[1]
        # Add HTTP Header
        http_response = HTTP_404
        # Append HTTP Body
        path = BASE_DIR + http_path
        if os.path.exists(path):
            if os.path.isdir(path):
                if os.path.isfile(path + INDEX_FILE):
                    http_response = get_body(filepath)
                else:
                    http_response = HTTP_403
            elif os.path.isfile(path):
                    http_response = get_body(path)
        # Send response
        conn.sendall(http_response)
        conn.close()

def get_body(filepath):
    with open(filepath) as f:
        http_response = HTTP_200 + f.read() + "\r\n"
        f.close()
    return http_response

if __name__ == "__main__":
    test()
    print "Bye"
