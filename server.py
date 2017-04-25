__version__ = "0.0.0"

import socket
import os
import magic
import mimetypes

# The following need to be set in server.conf
HOST = ""
PORT = 80
REQ_BUFFSIZE = 4096
BASE_DIR = "www"
INDEX_FILE = "index.html"
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
        if not http_request:
            print "Not a request"
            conn.close()
            continue
        else: http_path = http_request.split("\n",1)[0].split()[1]
        # Default not found
        http_response = HTTP_404
        # Find file
        path = BASE_DIR + http_path
        if os.path.isdir(path):
            if os.path.isfile(path + INDEX_FILE):
                http_response = get_head(path + INDEX_FILE) + get_body(path + INDEX_FILE)
            else:
                http_response = HTTP_403
        elif os.path.isfile(path):
                http_response = get_head(path) + get_body(path)
        # Send response
        conn.sendall(http_response)
        conn.close()

def get_body(filepath):
    with open(filepath) as f:
        http_body = f.read() + "\r\n"
        f.close()
        return http_body

def get_head(filepath):
    http_header = "HTTP/1.1 200 OK\r\nContent-Type: "
    http_header += get_file_type(filepath)
    http_header += "\r\n\r\n"
    return http_header

def get_file_type(filepath):
        name, ext = os.path.splitext(filepath)
        if ext in extensions_map:
            return extensions_map[ext]
        ext = ext.lower()
        if ext in extensions_map:
            return extensions_map[ext]
        if ext == '':
            return extensions_map['']
        # Use libmagic if unknown type
        else:
            return magic.from_file(filepath, mime=True)

# Populate MIME types dictionary
if not mimetypes.inited: mimetypes.init() # try to read system mime.types
extensions_map = mimetypes.types_map.copy()
extensions_map.update({
        '': 'application/octet-stream', # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        })

if __name__ == "__main__":
    test()
    print "Bye"
