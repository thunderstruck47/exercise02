#!/usr/bin/env python2
__version__ = "0.0.1"

# Standard modules
import socket
import os
import signal
import errno
import sys
import mimetypes
import datetime
import time
import shutil

if sys.version_info > (3, 0):
    import configparser
else:
    import ConfigParser

# Community modules
# Should be made optional
import magic

class HttpHandler():

    version = "1.0" # HTTP version
    supported_methods = ["GET", "HEAD", "POST"]
    responses = {
        200: "OK",
        400: "Bad Request",
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

    def __init__(self, conn, addr, server):
        # Not using version for now
        self.conn = conn
        self.addr = addr
        self.server = server
        self.server.headers = True
        self.handle_conn()

    # Handles current connection
    def handle_conn(self):
        request = None
        self.code = None
        try:
            self.conn.settimeout(None)
            self.rfile = self.conn.makefile('rb', -1)
            self.wfile = self.conn.makefile('wb', 0)
            try:
                firstline = self.rfile.readline(self.server.REQ_BUFFSIZE) # Ignore headers for now
                # write 414
                if not firstline:
                    self.server.close_connection = True
                    return
            except socket.timeout as e:
                self.server.close_connection = True
                raise
                return
            request = firstline.split()
            if len(request) == 3: # HTTP/1.0 AND HTTP/1.1
                method, path, version = request
                if version[:5] != "HTTP/":
                    self.write_code(400)
                try:
                    version_number = version.split("/",1)[1].split(".")
                    print version_number
                    if len(version_number) != 2:
                        raise ValueError
                    version_number = int(version_number[0]), int(version_number[1])
                    if version_number[0] < 1 or version_number[1] < 0:
                        raise ValueError

                except(ValueError, IndexError):
                    self.server.close_connection = True
                    self.write_code(400)
                else:
                    if version_number[0] > 1: # HTTP/2+
                        self.write_code(505) # Not supported
                    elif method not in self.supported_methods: # Valid method?
                        self.write_code(501)
                    else: # Proceeed
                        if version_number == (1, 0):
                            self.server.close_connection = True
                            self.version = "1.0"
                        elif version_number == (1, 1):
                            self.server.close_connection = False
                            self.version = "1.1"
                        path = self.handle_path(path)
                        if path: # File was found
                            self.handle_method(method, path)
            elif len(request) == 2:
                method, path = request
                if method == "GET":
                    self.server.close_connection = True
                    path = self.handle_path(path)
                    self.write_body(path)
            else:
                self.server.close_connection = True
                self.write_code(400)

        except:
            raise
            self.write_code(500) # Internal server error

        finally:
            # Logging
            if self.server.LOGGING and request: print("{0}:{1} - - [{2}] \"{3}\" {4} -".format(self.addr[0], self.addr[1], time.strftime("%d/%m/%Y %H:%M:%S", time.localtime()), firstline.strip("\r\n"), self.code))
            # Finalize files
            self.wfile.flush()
            self.rfile.close()
            self.wfile.close()

    def handle_method(self, method, path):
        self.write_code(200)
        if method == "GET" or method == "POST":
            self.write_head(path)
            self.write_body(path)
        elif method =="HEAD":
            self.write_head(path)

    def write_head(self, path):
        size, mtime = self.get_file_info(path)
        self.wfile.write("Content-Length: {0}\r\n".format(size))
        # if caching:
        #self.wfile.write("Last-Modified: {0}\r\n".format(self.httpdate(datetime.datetime.fromtimestamp(mtime))))
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

        if self.server.close_connection: self.wfile.write("Connection: close\r\n")
        else: self.wfile.write("Connection: keep-alive\r\n") # HTTP 1.0


    def handle_path(self, path):
        # Lose parameters
        path = path.split("?",1)[0]
        path = path.split("#",1)[0]
        path = os.path.abspath(path)
        path = self.server.PUBLIC_DIR + path
        if os.path.isdir(path):
            for index in self.server.INDEX_FILES:
                index = os.path.join(path, index)
                if os.path.isfile(index):
                    path = index
                    break
            else:
                # Is a dir
                self.server.close_connection = True
                self.write_code(403)
                return
        if os.path.isfile(path):
            return path
        path = path.rstrip("/")
        if os.path.isfile(path):
            return path
        # Not found
        self.server.close_connection = True
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
        self.configure(config_filename)
        # Setting up the HTTP handler
        self.handler = HttpHandler
        # Set up a socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.HOST, self.PORT))
        self.socket.listen(5)

    def configure(self, filepath):
        # Defaults:
        self.HOST = ""
        self.PORT = 8000
        self.REQ_BUFFSIZE = 4096
        self.PUBLIC_DIR = "www"
        self.HTTP_VERSION = 1.0
        self.INDEX_FILES = ["index.html","index.htm"]
        self.LOGGING = True
        self.LOG_FILE = "server.log"
        # Python 3.^
        if sys.version_info > (3, 0):
            config = configparser.ConfigParser()
            config.read(filepath)
            for key in config["server"]:
                try:
                    if key.upper() in ["PORT","REQ_BUFFSIZE"]: value = int(config["server"][key])
                    elif key.upper() == "INDEX_FILES": value = config["server"][key].split()
                    else: value = str(config["server"][key])
                    setattr(self, key.upper(), value)
                    #print(getattr(self, key.upper()))
                except ValueError:
                    raise
            print(self.REQ_BUFFSIZE)
        # Python 2.^
        else:
            try:
                with open(filepath,"rb") as f:
                    config = ConfigParser.ConfigParser()
                    config.readfp(f)
                    for pair in config.items("server"):
                        try:
                            key, value = pair[0], pair[1]
                            if key.upper() in ["PORT", "REQ_BUFFSIZE"]: value = int(value)
                            elif key.upper() == "INDEX_FILES": value = value.split()
                            elif key.upper() == "LOGGING": value = bool(value)
                            setattr(self, pair[0].upper(), value)
                            #print(getattr(self, pair[0].upper()))
                        except ValueError:
                            raise
            except IOError:
                # Should create a new config file
                print("* Missing configuration file")
                print("* Assuming default settings")

    def log(self, message):
        # To be implemented
        pass

    def _serve_non_persistent(self):
        print("* Serving HTTP at port {0} (Press CTRL+C to quit)".format(self.PORT))
        try:
            while True:
                pair = self.socket.accept()
                if pair: # Not None
                    conn, addr = pair
                    pid = os.fork()
                    if pid: # Parent
                        conn.close()
                    else: # Child
                        self.socket.close()
                        self.handler = HttpHandler(conn, addr, self)
                        conn.close()
                        os._exit(0)
        except KeyboardInterrupt:
            self.socket.close()
            sys.exit(0)

    def serve_single(self):
        print("* Waiting for a single HHTTP request at port {0}".format(self.PORT))
        conn, addr = self.socket.accept()
        if conn: self.handler = HttpHandler(conn, addr, self)
        conn.close()
        self.socket.close()

    def serve_persistent(self):
        self.conn = None
        self.connected = False
        self.close_connection = False
        print("* Serving HTTP at port {0} (Press CTRL+C to quit)".format(self.PORT))
        signal.signal(signal.SIGCHLD, self.signal_handler)
        try:
            while True:
                #print "Accepting connections..."
                if self.close_connection:
                        self.conn.close()
                        print("Closed connection")
                        #connected = False
                        os._exit(0)
                if not self.connected:
                    print("Accepting connections...")
                    try:
                        self.conn, addr = self.socket.accept()
                    except IOError as e:
                        code, msg = e.args
                        if code == errno.EINTR:
                            continue
                        else:
                            raise
                    if self.conn:
                        pid = os.fork()
                        if pid: # Parent
                            self.conn.close()
                        else:
                            self.socket.close()
                            print("Connecting...")
                            self.close_connection = False
                            self.connected = True
                            self.handler = HttpHandler(self.conn, addr, self)
                else:
                    print("Connected")
                    self.handler.handle_conn()
        except KeyboardInterrupt:
            if self.conn: self.conn.close()
            self.socket.close()

    def signal_handler(self, signum, frame):
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except OSError:
                return
            if pid == 0:
                return

if __name__ == "__main__":
    server = ForkingServer()
    #server.serve_single()
    #server._serve_non_persistent()
    server.serve_persistent()
    print("Bye")
