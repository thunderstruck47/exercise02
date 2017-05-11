#!/usr/bin/env python2
__version__ = "0.0.2"

# Standard modules
import socket
import os
import subprocess
import signal
import errno
import sys
import mimetypes
import datetime
import time
import shutil

# Import correct config parser
if sys.version_info > (3, 0):
    import configparser
else:
    import ConfigParser

# Community modules (optional)
try:
    import magic
except ImportError:
    pass

class HttpHandler():

    version = "HTTP/1.0" # HTTP version
    supported_methods = ["GET", "HEAD", "POST"]
    responses = {
        200: "OK",
        201: "Created",
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

    def __init__(self, server):
        self.server = server
        self.server.close_connection = True
        self.wfile = self.server.conn.makefile('wb', 0)
        if self.server.HTTP_VERSION == 1.1:
            self.version = "HTTP/1.1"
            self.server.close_connection = False
        elif self.server.HTTP_VERSION == 1.0:
            self.version = "HTTP/1.0"
        try:
            self.handle_conn()
        except socket.error as e:
            print("Socket error")

    # Handles current connection
    def handle_conn(self):
        request = None
        self.code = None
        self.cgi = None
        try:
            self.parse_request()
            if not self.code:
                self.server.close_connection = True
                self.wfile.close()
                print("{0}:{1} - - [{2}] Client disconnected -".format(self.server.addr[0], self.server.addr[1],  time.strftime("%d/%m/%Y %H:%M:%S", time.localtime())))
                return
            if self.code == 200:
                if not self.cgi: self.handle_request(self.method,self.path,self.version)
                else: self.handle_cgi(self.path)
            else:
                self.write_code(self.code)
                self.wfile.write(b"Content-Length: 0\r\n\r\n")
            # Flush and finalize file
            self.wfile.flush()
            if self.server.close_connection: self.wfile.close()
            # Logging
            if self.server.LOGGING: print("{0}:{1} - - [{2}] \"{3}\" {4} -".format(self.server.addr[0], self.server.addr[1], time.strftime("%d/%m/%Y %H:%M:%S", time.localtime()), self.status_line_string, self.code))
        except socket.error as e:
            if e.errno == errno.EPIPE:
                print("{0}:{1} - - [{2}] Connection interrupted (Broken pipe) -".format(self.server.addr[0], self.server.addr[1],  time.strftime("%d/%m/%Y %H:%M:%S", time.localtime())))
            return

    def parse_request(self):
        self.content_length = ""
        self.method = ""
        self.path = ""
        self.status_line_string = ""
        self.m_body = None
        request = self.server.conn.recv(self.server.REQ_BUFFSIZE) # Needs fixing
        request = request.decode().split("\r\n\r\n",1)
        # Check for body
        if len(request) >= 1: #Only header
            #if request[0] == "": return
            self.m_head = [x.strip() for x in request[0].split("\r\n")] # List of header fields
            self.status_line_string = self.m_head[0]
            self.status_line =  self.status_line_string.split()
            # Long method
            if len(self.status_line) == 3: # HTTP/1.0 AND HTTP/1.1
                method, path, version = self.status_line
                if self.valid_http_method(method) and self.valid_http_version(version):
                    if version == "HTTP/1.1" : self.server.close_connection = False
                    if version == "HTTP/1.0" : self.server.close_connection = True
                    for line in self.m_head[1:]:
                        self.should_keep_alive(line)
                    self.method = method
                    self.version = version
                    self.path = self.handle_path(path)
            elif len(self.status_line) == 2: #HTTP/0.9
                method, path = self.status_line
                self.version = "HTTP/0.9"
                self.server.close_connection = True
                if method == "GET":
                    self.method = method
                    self.path = self.handle_path(path)
                else:
                    self.code = 400
            else:
                self.server.close_connection = True
                self.code = 400
        # Needs caution
        # What if request contains only head
        if len(request) == 2 and self.method == "POST": #Prepare body
            self.m_body = request[1]
            size = len(body.encode('utf-8'))
            if size < self.content_length:
                self.m_body = self.m_body + self.conn.recv(self.content_length - size).decode()

    def should_keep_alive(self, line):
        try:
            field, value = [x.strip() for x in line.split(":")]
            if field.lower() == "connection":
                if value.lower() == "close":
                    self.server.close_connection = True
                    #print "Connection : close"
                    return True
                elif value.lower() == "keep-alive":
                    self.server.close_connection = False
                    #print "Connection : keep-alive"
                    return True
            elif field.lower() == "content-length":
                self.content_length = int(value)
            return False
        except:
            pass
            # Should be able to handle invalid headers

    def valid_http_version(self,version):
        if version[:5] != "HTTP/":
            #self.write_code(400)
            self.code = 400
            return False
        try:
            version_number = version.split("/",1)[1].split(".")
            if len(version_number) != 2:
                raise ValueError
            version_number = int(version_number[0]), int(version_number[1])
            if version_number[0] < 1 or version_number[1] < 0:
                raise ValueError

        except(ValueError, IndexError):
            self.server.close_connection = True
            self.code = 400
            #self.write_code(400)
            return False
        if version_number[0] > 1: # HTTP/2+
            self.code = 505
            #self.write_code(505) # Not supported
            return False
        if version != "HTTP/1.1" and version != "HTTP/1.0":
            self.code = 505
            self.server.close_connection = True
            return False
        return True

    def valid_http_method(self,method):
        if method not in self.supported_methods:
            self.code = 400
            return False
        return True

    def handle_cgi(self, path):
        env = {}
        env["SERVER_NAME"] = self.server.name
        env["SERVER_SOFTWARE"] = self.server.version_string
        env["GATEWAY_INTERFACE"] = "CGI/1.1"
        env["SERVER_PROTOCOL"] = self.version
        env["SERVER_PORT"] = str(self.server.PORT)
        env["REQUEST_METHOD"] = self.method
        env["REMOTE_ADDR"] = str(self.server.addr[0])
        env["REMOTE_PORT"] = str(self.server.addr[1])
        env["QUERY_STRING"] = self.query_string
        env["PATH_INFO"] = path
        env["SCRIPT_NAME"] = self.filename
        env["CONTENT_LENGTH"] = str(self.content_length)

        try:
            process = subprocess.Popen(["./" + path], stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, env = env)
            if self.m_body: stdin = self.m_body.encode()
            else: stdin = ""
            (output, err) = process.communicate(stdin)
            exit_code = process.wait()
            print err
            if exit_code == 1 or err: raise Exception
            self.write_code(self.code)
            self.wfile.write("Date: {0}\r\n".format(self.httpdate(datetime.datetime.utcnow())).encode())
            self.wfile.write("Server: {0}\r\n".format("Bistro/" + __version__).encode())
            self.wfile.write(output)
        except Exception:
            self.code = 500
            self.write_code(self.code)
            self.wfile.write(b"Content-Length: 0\r\n\r\n")

    def handle_request(self, method, path, version):
        self.write_code(self.code)
        if method == "GET":
            if version != "HTTP/0.9": self.write_head(path)
            self.write_body(path)
        elif method =="HEAD":
            self.write_head(path)
        elif method == "POST":
            self.handle_request("GET", path,version)


    def write_head(self, path):
        size, mtime = self.get_file_info(path)
        self.wfile.write("Content-Length: {0}\r\n".format(size).encode())
        # if caching:
        #self.wfile.write("Last-Modified: {0}\r\n".format(self.httpdate(datetime.datetime.fromtimestamp(mtime))))
        self.wfile.write("Content-Type: {0}\r\n".format(self.get_file_type(path)).encode())
        self.wfile.write("Date: {0}\r\n".format(self.httpdate(datetime.datetime.utcnow())).encode())
        self.wfile.write("Server: {0}\r\n\r\n".format("Bistro/" + __version__).encode())

    def write_body(self, path):
        f = open(path, "rb")
        shutil.copyfileobj(f,self.wfile)
        f.close()

    def write_code(self, code):
        if self.version != "HTTP/0.9": self.wfile.write("{0} {1} {2}\r\n".format(self.version, code, self.responses[code]).encode())
        else: self.wfile.write("{0} {1}\r\n".format(code, self.responses[code]).encode())
        #self.code = code
        if self.version != "HTTP/0.9":
            if self.server.close_connection: self.wfile.write("Connection: close\r\n".encode())
            else: self.wfile.write("Connection: keep-alive\r\n".encode()) # HTTP 1.0


    def handle_path(self, path):
        self.query_string = ""
        # Lose parameters
        path = path.split("#",1)[0]
        path = path.split("?",1)
        try:
            self.query_string = path[1]
        except:
            pass
        path = path[0]
        path = os.path.abspath(path)
        # CGI?
        if path.startswith("/cgi-bin/"):
            if os.path.isfile(self.server.PUBLIC_DIR + path):
                self.filename = os.path.basename(self.server.PUBLIC_DIR + path)
                self.code = 200
                self.cgi = True
                return self.server.PUBLIC_DIR + path
        path = self.server.PUBLIC_DIR + path
        if os.path.isdir(path):
            for index in self.server.INDEX_FILES:
                index = os.path.join(path, index)
                if os.path.isfile(index):
                    path = index
                    break
            else:
                # Is a dir
                #if os.path.dirname(path) == "www/uploads":
                #    code = 201
                #    return path
                self.code = 403
                return
        if os.path.isfile(path):
            self.code = 200
            return path
        path = path.rstrip("/")
        if os.path.isfile(path):
            self.code = 200
            return path
        # Not found
        self.code = 404

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
            try:
                return magic.from_file(filepath, mime=True)
            except Exception: # If magic was not imported
                return self.extensions_map[""]

    def reverse_file_type(self, filetype):
        for key, value in self.extensions_map.items():
            if value == filetype:
                return key
        return ""

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

class BaseServer():
    version_string = __version__
    name = "Bistro"

    def __init__(self, config_filename = "server.conf"):

        # Reading settings from config file
        # If setting is missing, replace with default
        self.configure(config_filename)
        # Setting up the HTTP handler
        self.handler = HttpHandler
        # Set up a socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.PORT = 8000
        self.socket.bind((self.HOST, self.PORT))
        self.socket.listen(1024) # Test queue

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
                    value = config["server"][key]
                    if key.upper() == "PORT" or key.upper() == "REQ_BUFFSIZE": value = int(value)
                    elif key.upper() == "HTTP_VERSION": value = float(config["server"][key])
                    elif key.upper() == "INDEX_FILES": value = config["server"][key].split()
                    else: value = str(config["server"][key])
                    setattr(self, key.upper(), value)
                    #print(getattr(self, key.upper()))
                except ValueError:
                    raise
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
                            elif key.upper() == "HTTP_VERSION": value = float(value)
                            elif key.upper() == "INDEX_FILES": value = value.split()
                            elif key.upper() == "LOGGING": value = bool(value)
                            setattr(self, pair[0].upper(), value)
                        except ValueError:
                            raise
            except IOError:
                # Should create a new config file
                print("* Missing configuration file")
                print("* Assuming default settings")

    def log(self, message):
        # To be implemented
        pass

    def serve_single(self):
        print("* Waiting for a single HHTTP request at port {0}".format(self.PORT))
        self.conn, self.addr = self.socket.accept()
        try:
            if self.conn: self.handler = HttpHandler( self)
        finally:
            self.conn.close()
            self.socket.close()

class ForkingServer(BaseServer):
    # Needs fixing
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
                        #self.conn.shutdown(SHUT_RDWR)
                        self.conn.close()
                        print("{0}:{1} - - [{2}] Closed connection -".format(self.addr[0], self.addr[1],  time.strftime("%d/%m/%Y %H:%M:%S", time.localtime())))
                        print("")
                        #connected = False
                        #print("Handler {0} - - [{1}] Closed".format(os.getpid(), time.strftime("%d/%m/%Y %H:%M:%S", time.localtime()))) 
                        os._exit(0)
                if not self.connected:
                    #print("Handler {0} - - [{1}] Accepting connections...".format(os.getpid(), time.strftime("%d/%m/%Y %H:%M:%S", time.localtime())))
                    try:
                        self.conn, self.addr = self.socket.accept()
                    except IOError as e:
                        code, msg = e.args
                        if code == errno.EINTR:
                            continue
                        else:
                            raise
                    if self.conn:
                        pid = os.fork() # Needs error handling
                        if pid != 0: # Parent
                            self.conn.close()
                        else:
                            self.socket.close()
                            print("{0}:{1} - - [{2}] Connecting... -".format(self.addr[0], self.addr[1], time.strftime("%d/%m/%Y %H:%M:%S", time.localtime()) ))
                            #self.close_connection = True
                            self.connected = True
                            self.handler = HttpHandler(self)
                else:
                    print("{0}:{1} - - [{2}] Already connected -".format(self.addr[0], self.addr[1],  time.strftime("%d/%m/%Y %H:%M:%S", time.localtime())))
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

class NonBlockingServer(BaseServer):
    pass

if __name__ == "__main__":
    server = ForkingServer("server.conf")
    #server.serve_single()
    #server._serve_non_persistent()
    server.serve_persistent()
    print("Bye")
