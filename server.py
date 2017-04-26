__version__ = "0.0.1"

import socket
import asyncore
import os
import magic
import mimetypes
import datetime
import time
import shutil
import ConfigParser

class HttpHandler():

    version = "1.0" # HTTP version
    supported_methods = ["GET", "HEAD", "POST"]
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

    def __init__(self, HTTP_VERSION = None, INDEX_FILES = ["index.htm", "index.html"], REQ_BUFFSIZE = 8192, PUBLIC_DIR = "www", LOGGING = True):
        # Not using version for now
        self.INDEX_FILES = INDEX_FILES
        self.REQ_BUFFSIZE = REQ_BUFFSIZE
        self.PUBLIC_DIR = PUBLIC_DIR
        self.LOGGING = LOGGING

    def handle_request(self, conn, addr):
        try:
            self.conn = conn
            self.addr = addr
            self.conn.settimeout(None)
            self.rfile = conn.makefile('rb', -1)
            self.wfile = conn.makefile('wb', 0)

            request =  self.rfile.readline(self.REQ_BUFFSIZE) # Ignore headers for now
            if request:
                method, path, version = request.split()
                if method not in self.supported_methods: # Check method before path
                    self.write_code(501)
                else:
                    path = self.handle_path(path)
                    if path: # File was found
                        self.handle_method(method, path)

        except:
            self.write_code(500) # Internal server error
            raise

        finally:
            # Logging
            if self.LOGGING and request: print("{0} - - [{1}] \"{2}\" {3} -".format(self.addr[0], time.strftime("%d/%m/%Y %H:%M:%S", time.localtime()), request.strip("\r\n"), self.code))
            if not request: print "emptry request"
            # Finalize files
            self.wfile.flush()
            self.rfile.close()
            self.wfile.close()
            self.conn.close()

    def handle_method(self, method, path):
        self.write_code(200)
        if method == "GET" or method == "POST":
            self.write_head(path)
            self.write_body(path)
        elif method =="HEAD":
            self.write_head(path)

    def write_head(self, path):
        size, mtime = self.get_file_info(path)
        self.wfile.write("Connection: close\r\n") # HTTP 1.0
        self.wfile.write("Content-Length: {0}\r\n".format(size))
        self.wfile.write("Last-Modified: {0}\r\n".format(self.httpdate(datetime.datetime.fromtimestamp(mtime))))
        self.wfile.write("Content-Type: {0}\r\n".format(self.get_file_type(path)))
        self.wfile.write("Date: {0}\r\n".format(self.httpdate(datetime.datetime.utcnow())))
        self.wfile.write("Server: {0}\r\n\r\n".format("Bistro/" + __version__))

    def write_body(self, path):
        f = open(path, "r")
        shutil.copyfileobj(f,self.wfile)
        f.close()

    def write_code(self, code):
        try:
            self.wfile.write("HTTP/{0} {1} {2}\r\n".format(self.version, code, self.responses[code]))
            self.code = code
        except:
            self.write_code(500)
            self.code = 500
            raise

    def handle_path(self, path):
        # Lose parameters
        path = path.split("?",1)[0]
        path = path.split("#",1)[0]
        path = self.PUBLIC_DIR + path
        if os.path.isdir(path):
            for index in self.INDEX_FILES:
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

    def get_file_info(self, filepath):
        f = open(filepath,'rb')
        fs = os.fstat(f.fileno())
        size = fs.st_size
        mtime = fs.st_mtime
        f.close()
        return size, mtime

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

    def __init__(self, config_filename = "server.conf"):

        # Reading settings from config file
        # If setting is missing, replace with default
        try:
            with open(config_filename,"rb") as f:
                config = ConfigParser.ConfigParser()
                config.readfp(f)
                try:
                    self.HOST = config.get("server","host")
                except:
                    self.HOST = ""
                try:
                    self.PORT = config.getint("server","port")
                except:
                    self.PORT = 8000
                try:
                    self.REQ_BUFFSIZE = config.getint("server","request_buffsize")
                except:
                    self.REQ_BUFFSIZE = 4096
                try:
                    self.PUBLIC_DIR = config.get("server","public_dir")
                except:
                    self.PUBLIC_DIR = "www"
                try:
                    self.HTTP_VERSION = config.get("server","http_version")
                except:
                    self.HTTP_VERSION = 1.0
                try:
                    self.INDEX_FILES = config.get("server","index_files").split()
                except:
                    self.INDEX_FILES = ["index.html","index.htm"]
                try:
                    self.LOGGING = config.getboolean("server","logging")
                except:
                    self.LOGGING = True
                try:
                    self.LOG_FILE = config.get("server","log_file")
                except:
                    self.LOG_FILE = "server.log"

                f.close()
                # Setting up the HTTP handler
                self.handler = HttpHandler(self.HTTP_VERSION, self.INDEX_FILES, self.REQ_BUFFSIZE, self.PUBLIC_DIR)

        except IOError:
            # Should create a new config file
            print "Missing configuration file"
            print "Assuming default settings"
            self.handler = HttpHandler()

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
                    self.handler.handle_request(conn, addr)
                    os._exit(0)

if __name__ == "__main__":
    server = ForkingServer()
    server.serve_forever()
    print "Bye"
