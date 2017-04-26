__version__ = "0.0.1"

import socket
import asyncore
import os
import magic
import mimetypes
import datetime
import time
import shutil

# The following need to be set in server.conf
HOST = ""
PORT = 80
REQ_BUFFSIZE = 8192
BASE_DIR = "www"

class HttpHandler():

    __version__ = "1.0" # HTTP version
    line_terminator = "\r\n" # Unused
    responses = {
        200: "OK",
        403: "Forbidden",
        404: "Not Found",
        500: "Internal Server Error",
        501: "Not Implemented",
        505: "HTTP Version Not Supported"
    }
     # Populate MIME types dictionary
    if not mimetypes.inited: mimetypes.init() # try to read system mime.types
    extensions_map = mimetypes.types_map.copy()
    extensions_map.update({
        '': 'application/octet-stream', # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        })

    def __init__(self,conn):
        self.conn = conn
        self.conn.settimeout(None)
        self.rfile = conn.makefile('rb', -1)
        self.wfile = conn.makefile('wb', 0)

    def handle_request(self):
        try:
            request =  self.rfile.readline(REQ_BUFFSIZE) # Ignore headers for now
            if request:
                method, path, version = request.split()
                path = self.handle_path(path)
                if path: # File was found
                    self.handle_method(method, path)
        except:
            self.write_code(500)
            raise
        finally:
            self.wfile.flush()
            self.rfile.close()
            self.wfile.close()
            self.conn.close()

    def handle_method(self, method, path):
        if method == "GET":
            self.write_code(200)
            self.write_head(path)
            self.write_body(path)
        elif method =="HEAD":
            self.write_code(200)
            self.write_head(path)
        elif method =="POST":
            # Works the same as GET
            self.write_code(200)
            self.write_head(path)
            self.write_body(path)
        else: self.write_code(501)

    def write_head(self, path):
        self.wfile.write("Content-Type: {0}\r\n".format(self.get_file_type(path)))
        self.wfile.write("Date: {0}\r\n".format(self.httpdate(datetime.datetime.utcnow())))
        self.wfile.write("Server: {0}\r\n\r\n".format("Bistro/" + __version__))

    def write_body(self, path):
        f = open(path, "r")
        shutil.copyfileobj(f,self.wfile)
        f.close()

    def write_code(self, code):
        try:
            self.wfile.write("HTTP/{0} {1} {2}\r\n".format(self.__version__, code, self.responses[code]))
        except:
            self.write_code(500)
            raise

    def handle_path(self, path):
        # Lose parameters
        path = path.split("?",1)[0]
        path = path.split("#",1)[0]
        path = BASE_DIR + path
        if os.path.isdir(path):
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.isfile(index):
                    path = index
                    break
            else:
                # Is a dir
                self.write_code(403)
                return
        if os.path.isfile(path):
            return path
        path = path.rstrip("/")
        if os.path.isfile(path):
            return path
        # Not found
        self.write_code(404)

    def get_file_type(self, filepath):
        name, ext = os.path.splitext(filepath)
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        ext = ext.lower()
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        if ext == "":
            return self.extensions_map[""]
        # Use libmagic if unknown type
        else:
            return magic.from_file(filepath, mime=True)

    def httpdate(self, dt):
        """Return a string representation of a date according to RFC 1123
        (HTTP/1.1).

        The supplied date must be in UTC.

        """
        weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()]
        month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
                 "Oct", "Nov", "Dec"][dt.month - 1]
        return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (weekday, dt.day, month,
            dt.year, dt.hour, dt.minute, dt.second)

class ForkingServer():

    def __init__(self, HOST, PORT):
        self.PORT = PORT
        self.HOST = HOST

    def configure(self):
        pass

    def setup(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.HOST, self.PORT))
        self.socket.listen(5)

    def serve_forever(self):
        self.setup()
        print("* Serving HTTP at port {0} (Press CTRL+C to quit)".format(self.PORT))

        while True:
            pair = self.socket.accept()
            if pair: # Not None
                conn, addr = pair
                pid = os.fork()
                if pid: # Parent
                    conn.close()
                else: # Child
                    self.socket.close()
                    handler = HttpHandler(conn)
                    handler.handle_request()
                    os._exit(0)

if __name__ == "__main__":
    server = ForkingServer(HOST,PORT)
    server.serve_forever()
    print "Bye"
