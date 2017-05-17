#!/usr/bin/env python
"""\
TODO: About
"""

__name__ = "bistro"
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
# Non-blocking IO
import select
# Multiprocessing (not used)
import multiprocessing
# Import correct config parser and queue
if sys.version_info > (3, 0):
    import configparser
    import queue as queue
else:
    import ConfigParser
    import Queue as queue
# Community modules (optional)
try:
    import magic
except ImportError:
    pass
# TODO: Should use in future
#try:
#    from cStringIO import StringIO
#except ImportError:
#    from StringIO import StringIO
from io import BytesIO

class HttpHandler():
    """ TODO """
    
    # NOTE: HttpHandler is implemented as a State Machine with six stages,
    # three main stages and three sub-stages. The main stages (set below)
    # define states where we should check the buffer for data. Their use
    # is to answer the questions - Is status line recieved?, Are headers
    # recieved?, Is the body recieved? - represented by the methods - 
    # status_line_recieved(), headers_recieved(), body_recieved(). The
    # minor stages are used to process the respective part of the request.
    STAGE1 = -1
    STAGE2 = 0
    STAGE3 = 1
   
    # XXX: Using StringIO rather than lists of string objects returned by
    # recv() minimizes memory usage and fragmentation that occurs when
    # rbufsize is large compared to the typical return value of recv().
    # SOURCE: https://svn.python.org/projects/python/trunk/Lib/socket.py
    def reset_buffer(self):
        """init and reset socket data buffer"""
        self.__input_buffer = b''
   
   # Current request variables. When done, should be cleared with refresh()
    def refresh(self):
        """init and reset current request variables"""
        self.__status_line = b''
        self.__headers = []
        self.__response = b''
        self.__method = ''
        self.__path = ''
        self.__version = ''
        self.__content_length = ''
        self.__cgi = False
        self.__stage = self.STAGE1
    
    # The outgoing message queue
    response_queue = queue.Queue()
    # List of supported methods and a dictionarry of supported response codes
    __supported_methods = ['GET', 'HEAD', 'POST']
    __responses = {
        200: 'OK',
        201: 'Created',
        400: 'Bad Request',
        403: 'Forbidden',
        404: 'Not Found',
        414: 'Request URI Too Long',
        500: 'Internal Server Error',
        501: 'Not Implemented',
        505: 'HTTP Version Not Supported'
    }

    # CRLF
    __lt = b'\r\n'

    # Populate MIME types dictionary
    if not mimetypes.inited: mimetypes.init() # try to read system mime.types
    extensions_map = mimetypes.types_map.copy()
    extensions_map.update({
        '': 'application/octet-stream', # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        })

    def __init__(self,conn,server):
        """conn stands for connection"""
        self.server = server
        self.conn = conn
        self.addr = conn.getpeername()
        self.close = True
        # Create current reques variables
        self.refresh()
        # Create input buffer
        self.reset_buffer()
        # XXX: validate?
        if self.server.HTTP_VERSION == 1.1: self.version = 'HTTP/1.1'
        elif self.server.HTTP_VERSION == 1.0: self.version = 'HTTP/1.0'

    def handle(self):
        """this class operates our state machine"""
        # Recv data from socket
        self.recv()
        # Check stage
        if self.__stage == self.STAGE1:
            if self.status_line_recieved():
                if self.status_line_parse():
                    if self.__version == 'HTTP/0.9':
                        self.queue_file()
                        self.__stage = self.STAGE1
                    else:
                        self.__stage = self.STAGE2
                #ekse error was sent
        if self.__stage == self.STAGE2:
            if self.headers_recieved():
                print(self.headers_parse)
                if self.headers_parse():
                    self.queue_file()
                    
                    # if self.__content_length = '0' or \
                    #        self.__content_length = '':
                    #   do prepare response
                    #   do queue response
                    #   do refresh()
                    #   do go_to_stage -1
                    #else goto next stage
                    self.__stage = self.STAGE1 #3
                else:
                    # error was send
                    self.__stage = self.STAGE1
        if self.__stage == self.STAGE3:
            self.refresh()
            pass

    def recv(self):
        """returns void"""
        # Read until the socket blocks
        while True:
            try:
                data = self.conn.recv(self.server.REQ_BUFFSIZE)
                if data: self.__input_buffer += data
                else:
                # XXX:client closed connection, should do more
                    self.server.shutdown_connection(self.conn)
                    break
                if len(data) < self.server.REQ_BUFFSIZE: break
            # Break the loop if EWOULDBLOCK
            except (socket.error, IOError) as e:
                if e.errno == errno.EINTR: continue # retry recv call
                elif e.errno != errno.EWOULDBLOCK: raise # should close connection
                break #EWOULDBLOCK
    
    def send(self):
        """returns void"""
        pass

    def status_line_recieved(self):
        """returns True if status line was recieved"""
        try:
            self.__status_line, self.__input_buffer = \
                    self.__input_buffer.split(self.__lt,1)
            return True
        except ValueError:
            # XXX: should be a different value i.e.: 
            # MAXLENURL, LENURL, MAXURL, URILEN, MAXURILEN
            if len(self.__input_buffer) > self.server.REQ_BUFFSIZE:
                self.send_error(414)
                self.refresh()
                # NOTE: Reset input buffer
                self.reset_buffer()
            return False
    
    def status_line_parse(self):
        """returns True if request is valid""" 
        status_line = self.__status_line.decode()
        status_line = status_line.split(' ')
        print(status_line)
        # HTTP/1.0 and HTTP/1.1
        if len(status_line) == 3:
            self.__method, self.__path, self.__version = status_line
            if self.validate_version() and self.validate_method() \
                    and self.validate_path(): return True
        # HTTP/0.9
        elif len(status_line) == 2:
            print("TUK")
            self.__version = 'HTTP/0.9'
            self.__method, self.__path = status_line
            if self.__method == 'GET' and self.validate_path(): \
                    return True
            self.send_error(400)
        # Bad request
        else: self.send_error(400)
        # Request is invalid
        self.__version = self.version
        return False

    def validate_version(self,version = None):
        # NOTE: Useful for unit testing later on
        if not version: version = self.__version
        # XXX: Do I really need all that fuss below? 
        if version[:5] != "HTTP/":
            self.send_error(400)
            return False
        try:
            version_number = version.split("/",1)[1].split(".")
            if len(version_number) != 2:
                raise ValueError
            version_number = int(version_number[0]), int(version_number[1])
            if version_number[0] < 1 or version_number[1] < 0:
                raise ValueError
        except(ValueError, IndexError):
            self.send_error(400)
            return False
        if version_number[0] > 1: # HTTP/2+
            self.send_error(505) # Not supported
            return False
        if version != "HTTP/1.1" and version != "HTTP/1.0":
            self.send_error(505) # Bad HTTP version
            return False
        if version == "HTTP/1.1": # Change default close
            self.close = False
        return True

    def validate_method(self,method = None):
        if not method: method = self.__method
        if method not in self.__supported_methods:
            self.send_error(400)
            return False
        return True
 
    def validate_path(self,path = None):
        if not path: path = self.__path
        # FIXME: Losely based on previous version - needs error handling!
        # FIXME: status_line = ['GET', ''] ?
        if path == '' or path == ' ': return False
        # XXX: Check path input /cgi-bin/script.py\/
        # XXX: Is injection possible?
        # TODO: Unit tests on all methods
        # Lose parameters:
        path = path.split("#",1)[0]
        path = path.split("?",1)
        try:
            self.__query_string = path[1]
        except:
            self.__query_string = ''
        print(self.__query_string)
        path = path[0]
        path = os.path.abspath(path)
        path = self.server.PUBLIC_DIR + path
        print(path)
        # CGI?
        # FIXME: Replace input with configurable i.e. CGIDIR, DIRCGI, CGIPATH
        if path.startswith(self.server.PUBLIC_DIR + "/cgi-bin/"):
            if os.path.isfile(path):
                self.__filename = os.path.basename(path)
                self.__cgi = True
                self.__path = path
                return True
        # Directory?
        if os.path.isdir(path):
            for index in self.server.INDEX_FILES:
                index = os.path.join(path, index)
                if os.path.isfile(index):
                    path = index
                    break
            else:
                self.send_error(403)
                return False
        # File?
        if os.path.isfile(path):
            self.__path = path
            return True
        # Strip /; check again
        path = path.rstrip("/")
        if os.path.isfile(path):
            self.__path = path
            return True
        # Not found
        self.send_error(404)
        return False
 

    def headers_recieved(self):
        """returns True if headers were received"""
        # FIXME: Should validate headers, ignore bad headers, or send 400
        try:
            #if self.__input_buffer.startswith(b'\r\n'):
            #    #self.__input_buffer.lstrip(b'\r\n')
            #    print("asd")
            #    return True
            while True:
                header, self.__input_buffer = \
                        self.__input_buffer.split(self.__lt, 1)
                if not header: break
                self.__headers.append(header)
            return True
        except ValueError:
            return False
    
    def headers_parse(self):
        # XXX: Currently ignores badly formed request headers
        # FIXME: Should close connection in HTTP/1.0 unless keep-alive was
        # specified.
        for line in self.__headers:
            print(line)
            try:
                f, v = [x.strip() for x in line.decode().split(":",1)]
                if f.lower() == "connection":
                    if v.lower() == "close":
                        self.close = True
                        #self.add_header("Connection","close")
                    elif v.lower() == "keep-alive": 
                        self.close = False
                        #self.add_header("Connection","close")
                elif f.lower() == "content-length": self.__content_length = v
                elif f.lower() == "content-type": self.__content_type = v
            except:
                # XXX: Should handle this
                pass
        return True

    def send_error(self,code):
        """adds error to response queue"""
        # TODO: Validate?
        try:
            message = self.__responses[code]
        except KeyError:
            message = '???'
        self.add_response(code, message)
        if self.__version != 'HTTP/0.9':
            if self.close: self.add_header('Connection','close')
            else: self.add_header('Connection','keep-alive')
            self.add_header('Content-length','0')
        self.add_end_header()
        self.queue_response()
        # TODO: Add message boyd
    
    def queue_response(self):
        """adds current response to response queue"""
        self.response_queue.put(self.__response)
        self.refresh()
    
    def queue_file(self):
        """adds a file to response queue"""
        try:
            with open(self.__path,'rb') as f:
                f = f.read()
                f = bytes(f)
                self.add_response(200,'OK')
                if self.close: self.add_header('Connection','close')
                else: self.add_header('Connection','keep-alive')
                self.__response += f
                self.queue_response()
        except IOError as e:
            self.send_error(500)

    def add_response(self, code, message):
        """writes response status code and default headers"""
        if len(self.__response) != 0: self.refresh() # Possibly not needed
        if self.__version == 'HTTP/0.9':
            self.__response += '{0} {1}\r\n'.format(code,message).encode()
        else:
            # XXX: Should we switch versions?
            self.__response += '{0} {1} {2}\r\n'.format(
                    self.__version,code,message).encode()
            self.add_header('Date', self.date_time_string())
            self.add_header('Server', self.server_string())
            
        # Should be done later:
        #if self.close: self.add_header("Connection", "close")
        #else: self.add_header("Connection", "keep-alive")

    def add_header(self,name,value):
        # XXX: Should validate
        self.__response += '{0}:{1}'.format(
                name.strip(),value.strip()).encode()
        self.add_end_header()
    
    def add_end_header(self):
        self.__response += self.__lt

    def server_string(self):
        """returns server name and version"""
        return __name__ + '/' + __version__
    
    def date_time_string(self):
        """returns current date time"""
        return self.httpdate(datetime.datetime.utcnow())

    def httpdate(self, dt):
        """Return a string representation of a date according to RFC 1123
        (HTTP/1.1).

        The supplied date must be in UTC.

        """
        weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] \
                [dt.weekday()]
        month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
                 "Oct", "Nov", "Dec"][dt.month - 1]
        return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (weekday, dt.day, month,
            dt.year, dt.hour, dt.minute, dt.second)


    def finalize(self):
        if not self.wfile.closed:
            try:
                self.wfile.flush()
            except:
                pass
            self.wfile.close()
        self.rfile.close()
        self.server.shutdown_connection(self.conn)

    def handle_connection(self):
        try:
            while not self.close:
                    self.parse_request()
                    self.handle_one_request()
            self.finalize()
        except socket.error as e:
            self.close = True
            if e.errno == errno.EPIPE:
                print("{0}:{1} - - [{2}] Connection interrupted (Broken pipe) -".format(self.addr[0], self.addr[1],  time.strftime("%d/%m/%Y %H:%M:%S", time.localtime())))
            

    # Handles current connection
    def handle_one_request(self):
        #self.cgi = None
        #self.parse_request()
        # If an empty byte was sent: close the connection
        if not self.code:
            self.close = True
            print("{0}:{1} - - [{2}] Client disconnected -".format(self.addr[0], self.addr[1],  time.strftime("%d/%m/%Y %H:%M:%S", time.localtime())))
            return
        if self.code == 200:
            if not self.cgi: self.handle_request(self.method,self.path,self.version)
            else: self.handle_cgi(self.path)
        else:
            self.write_code(self.code)
            self.wfile.write(b"Content-Length: 0\r\n\r\n")
        # Logging
        if self.server.LOGGING: print("{0}:{1} - - [{2}] \"{3}\" {4} -".format(self.addr[0], self.addr[1], time.strftime("%d/%m/%Y %H:%M:%S", time.localtime()), self.status_line_string, self.code))

    def parse_request(self):
        self.content_length = 0
        self.content_type = ""
        self.method = ""
        self.path = ""
        self.m_body = None
        self.code = None
        self.cgi = None
        # Preparing message status line
        self.status_line_string = self.rfile.readline(self.server.REQ_BUFFSIZE + 1).decode()
        self.status_line_string = self.status_line_string.rstrip("\r\n")
        if len(self.status_line_string) > self.server.REQ_BUFFSIZE: # Rquest URI too long
            self.code = 414
            return True
        elif self.status_line_string == "": # Client sent empty request: terminate connection
            return False
        #print(self.status_line_string)
        # Preparing message headers
        self.m_head = []
        while True:
            select.select([self.conn], [], [])
            line = self.rfile.readline(self.server.REQ_BUFFSIZE) # Too long?
            self.m_head.append(line.rstrip(b"\r\n").decode())
            print(line)
            if line == b"\r\n": break
        print(len(self.m_head))
        # Processing
        self.status_line =  self.status_line_string.split()

        # HTTP/1.0 and HTTP/1.1
        if len(self.status_line) == 3:
            method, path, version = self.status_line
            if self.valid_http_method(method) and self.valid_http_version(version):
                if version == "HTTP/1.1" : self.close = False
                if version == "HTTP/1.0" : self.close = True
                for line in self.m_head:
                    self.parse_header(line)
                self.method = method
                self.version = version
                self.path = self.handle_path(path)

        # HTTP/0.9
        elif len(self.status_line) == 2:
            method, path = self.status_line
            self.version = "HTTP/0.9"
            self.close = True
            if method == "GET":
                self.method = method
                self.path = self.handle_path(path)
            else:
                self.code = 400

        # Invalid request
        else:
            self.close = True
            self.code = 400

        # If POST and message body
        if self.method == "POST" and self.content_length > 0: #Prepare body
            self.m_body = self.rfile.read(self.content_length)
        return True

    def parse_header(self, line):
        try:
            field, value = [x.strip() for x in line.split(":",1)]
            if field.lower() == "connection":
                if value.lower() == "close":
                    self.close = True
                elif value.lower() == "keep-alive":
                    self.close = False
            elif field.lower() == "content-length":
                self.content_length = int(value)
            elif field.lower() == "content-type":
                self.content_type = str(value)
        except:
            pass
            # Should be able to handle invalid headers

    def valid_http_version(self,version):
        if version[:5] != "HTTP/":
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
            self.close = True
            self.code = 400
            return False
        if version_number[0] > 1: # HTTP/2+
            self.code = 505
            return False
        if version != "HTTP/1.1" and version != "HTTP/1.0":
            self.code = 505
            self.close = True
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
        env["REMOTE_ADDR"] = str(self.addr[0])
        env["REMOTE_PORT"] = str(self.addr[1])
        env["QUERY_STRING"] = self.query_string
        env["PATH_INFO"] = path
        env["SCRIPT_NAME"] = self.filename
        env["CONTENT_LENGTH"] = str(self.content_length)
        env["CONTENT_TYPE"] = self.content_type

        try:
            process = subprocess.Popen(["./" + path], stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, env = env)
            if self.m_body: stdin = self.m_body
            else: stdin = ""
            (output, err) = process.communicate(stdin)
            exit_code = process.wait()
            if exit_code == 1 or err:
                print("ERROR calling \"{0}\":\r\n {1}".format(env["SCRIPT_NAME"],err.decode()))
                raise Exception
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

class BaseServer(object):
    version_string = __version__
    name = __name__

    def __init__(self, config_filename = "server.conf"):

        # Reading settings from config file
        # CAUTION path/filename?
        self.configure(config_filename)
        # Setting up the HTTP handler
        self.handler = HttpHandler
        # Set up a socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.HOST, self.PORT))
        self.socket.listen(5) # Should be set in confing / Test it

    def configure(self, filepath):
        # Defaults:
        self.HOST = ""
        try:
            self.PORT = 8000
        except:
            pass
        self.REQ_BUFFSIZE = 65536
        self.PUBLIC_DIR = "www"
        self.HTTP_VERSION = 1.0
        self.INDEX_FILES = ["index.html","index.htm"]
        self.LOGGING = True
        self.LOG_FILE = "server.log"

        if os.path.isfile(filepath):
            # Python 3.^
            if sys.version_info > (3, 0):
                config = configparser.ConfigParser()
                config.read(filepath)
                if "server" in config:
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
                else:
                    print("* Wrong or incorrect configuration")
                    print("* Assuming default settings")
            # Python 2.^
            else:
                with open(filepath,"rb") as f:
                    config = ConfigParser.ConfigParser()
                    config.readfp(f)
                    try:
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
                    except ConfigParser.NoSectionError:
                        print("* Wrong or incorrect configuration")
                        print("* Assuming default settings")

        else:
            # Should create a new config file
            print("* Missing configuration file")
            print("* Assuming default settings")

    def log(self, message):
        # To be implemented
        pass

    def serve_single(self):
        print("* Waiting for a single HTTP request at port {0}".format(self.PORT))
        self.conn, self.addr = self.socket.accept()
        try:
            if self.conn: self.handler = HttpHandler( self)
        finally:
            self.shutdown_connection()
            self.socket.close()

    def shutdown_connection(self, conn):
        try:
            # explicit shutdown
            conn.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        conn.close()


class ForkingServer(BaseServer):
    # Needs fixing
    def _serve_non_persistent(self):
        print("* Serving HTTP at port {0} (Press CTRL+C to quit)".format(self.PORT))
        try:
            while True:
                conn, addr = self.socket.accept()
                if conn: # Not None
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
        #self.connected = False
        #self.close_connection = False
        print("* Serving HTTP at port {0} (Press CTRL+C to quit)".format(self.PORT))
        signal.signal(signal.SIGCHLD, self.signal_handler)
        try:
            while True:
                try:
                    pair = self.socket.accept()
                except IOError as e:
                    code, msg = e.args
                    if code == errno.EINTR:
                        continue
                    else:
                        raise
                if pair:
                    self.conn, self.addr = pair
                    pid = os.fork() # Needs error handling
                    if pid != 0: # Parent
                        # close the file descriptor
                        self.conn.close()
                    else:
                        self.socket.close()
                        self.handler = HttpHandler(self.conn,self)
                        self.handler.handle_connection()
                        del self.handler
                        os._exit(0)
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
    def __init__(self, config = "server.conf"):
        # Initializing base server config
        super(self.__class__, self).__init__(config)

        # Set socket to non-blocking
        self.socket.setblocking(0)

        # Sockets from which we expect to read
        self.inputs = [self.socket]

        # Sockets to which we expect to write
        self.outputs = []

        # Current handlers queue (HttpHandler:Queue)
        self.handlers = {}

    def serve_persistent(self):
        print("* Serving HTTP at port {0} (Press CTRL+C to quit)".format(self.PORT))
        try:
            while self.inputs:
                # Wait for at least one socket to be ready for processing
                # Needs error handling (Keyboard Interrupt)
                readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs)   

                # Handle inputs
                for s in readable:
                    if s is self.socket:
                        # Server is ready to accept a connection
                        conn, addr = self.socket.accept()
                        # Set to non-blocking
                        conn.setblocking(0)
                        self.inputs.append(conn)

                        # Give the connection a queue for the handlers
                        self.handlers[conn] = queue.Queue()
                    else: # Read from connection
                        # Creates a new HttpHandler object.
                        # WARNING: Slows down persistent connections.
                        # Needs to be managed differently.
                        try:
                            handler = HttpHandler(s,self)
                            # Check if request was parsed successfuly
                            if handler.parse_request():
                                # Add handler to queue
                                self.handlers[s].put(handler)
                                if s not in self.outputs:
                                    self.outputs.append(s)
                            else:
                                self.clear(s)
                                if s in writable:
                                    writable.remove(s)
                        except:
                            self.clear(s)
                
                # Handle outputs
                for s in writable:
                    print (self.handlers[s].qsize())
                    try:
                        next_handler = self.handlers[s].get_nowait()
                    except (queue.Empty):
                        self.outputs.remove(s)
                    except (KeyError):
                        pass
                    else:
                        next_handler.handle_one_request()
                        if next_handler.close:
                            self.clear(s)
                            if s in self.inputs:
                                self.inputs.remove(s)
                # Handle "exceptional conditions"
                for s in exceptional:
                    self.clear(s)

        except KeyboardInterrupt:
            self.clear(self.socket)

    def clear(self,connection):
        if connection in self.outputs:
            self.outputs.remove(connection)
        if connection in self.inputs:
            self.inputs.remove(connection)
        #self.shutdown_connection(connection)

        if connection in self.handlers:
            del self.handlers[connection]

if __name__ == "bistro":
    server = ForkingServer()
    conn, _ = server.socket.accept()
    conn.setblocking(False)
    handler = HttpHandler(conn,server)
    while True:
        r,w,e = select.select([conn],[],[])
        handler.handle()
        print (handler.response_queue.qsize())
        try:
            r = handler.response_queue.get_nowait()
        except (queue.Empty):
            pass
        except (KeyError):
            pass
        else:
            conn.send(r)
            #conn.send(r)

    #server = MultiprocessingServer()
    #server = MPNblockServer()
    #server = NonBlockingServer()
    #server.serve_persistent()
    print("Bye")
