#!/usr/bin/env python
"""\
TODO: About
"""

__servername__ = "bistro"

__version__ = "0.0.2"

__all__ = [ "HttpHandler", "ForkingServer", "NonBlockingServer"]

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
from io import open
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
    DEBUG = True
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
        self.__input_buffer = ''
   
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
    __lt = '\r\n'

    # Populate MIME types dictionary
    if not mimetypes.inited: mimetypes.init() # try to read system mime.types
    extensions_map = mimetypes.types_map.copy()
    extensions_map.update({
        '': 'application/octet-stream', # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        })

    def __init__(self,conn=None,server=None):
        """conn stands for connection"""
        if server: 
            self.server = server
            # XXX: validate?
            if self.server.HTTP_VERSION == 1.1: self.version = 'HTTP/1.1'
            elif self.server.HTTP_VERSION == 1.0: self.version = 'HTTP/1.0'
            self.__version = self.version
        if conn:
            self.conn = conn
            self.addr = conn.getpeername()
        self.close = True
        self.finished = False
        # Create current reques variables
        self.refresh()
        # Create input buffer
        self.reset_buffer()
    
    def handle_connection(self):
        if self.close: self.finished = True

    def handle(self):
        """this class operates our state machine"""
        #self.finished = False
        # Recv data from socket
        if not self.recv(): 
            self.handle_connection()
            return False
        # Check stage
        if self.__stage == self.STAGE1:
            if self.DEBUG: print("-----STAGE 1-----")
            if self.status_line_recieved():
                if self.DEBUG: print("Status line received:\r\n" \
                        + self.__status_line)
                if self.status_line_parse():
                    if self.DEBUG: print("Status line parsed")
                    if self.__version == 'HTTP/0.9':
                        self.queue_file()
                        self.handle_connection()
                        self.__stage = self.STAGE1
                    else:
                        self.__stage = self.STAGE2
                #else:
                    #print("handling")
                    #self.handle_connection()
                #error was sent
        if self.__stage == self.STAGE2:
            if self.DEBUG: print("-----STAGE 2-----")
            if self.headers_recieved():
                if self.DEBUG: print("Headers received:\r\n" + str(self.__headers))
                if self.headers_parse():
                    if self.DEBUG: print("Headers parsed")
                    self.queue_file()
                    if self.DEBUG: 
                        print("Queued files:" + str(self.response_queue.qsize()))
                    self.handle_connection()
                    if self.DEBUG: 
                        print("Close:" + str(self.close))
                        print("Finished:" + str(self.finished))
                    self.__stage = self.STAGE3 #3
                else:
                    #self.handle_connection()
                    self.__stage = self.STAGE1
        if self.__stage == self.STAGE3:
            self.refresh()
            self.__stage = self.STAGE1
            pass
        return True

    def recv(self):
        """returns void"""
        # Read until the socket blocks
        if self.DEBUG: print("Receiving..")
        while True:
            try:
                data = self.conn.recv(self.server.REQ_BUFFSIZE)
                #if self.DEBUG: print("Received data: \r\n" + data.decode())
                if data: self.__input_buffer += data.decode()
                else:
                # NOTE:client closed connection
                    self.close = True
                    return False
                if len(data) < self.server.REQ_BUFFSIZE: break
            # Break the loop if EWOULDBLOCK
            except (socket.error, IOError) as e:
                if e.errno == errno.EINTR: continue # retry recv call
                elif e.errno != errno.EWOULDBLOCK:
                    self.close = True
                    return False# should close connection
            except (UnicodeDecodeError) as e:
                self.close = True
                return False
        return True
    
    def send(self):
        """returns void"""
        try:
            next_response = self.response_queue.get_nowait()
        except (queue.Empty):
            if self.DEBUG: print("Queue is empty")
            return False
        else:
            # XXX: Needs error handling
            self.conn.send(next_response)
            #print("{0}:{1} - - [{2}] \"{3}\" {4} -".format(self.addr[0], self.addr[1], time.strftime("%d/%m/%Y %H:%M:%S", time.localtime()), next_response.decode().split('\r\n',1)[0], self.code))
            return True


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
        status_line = self.__status_line
        status_line = status_line.split(' ')
        print(status_line)
        # HTTP/1.0 and HTTP/1.1
        if len(status_line) == 3:
            self.__method, self.__path, self.__version = status_line
            if self.validate_version() and self.validate_method() \
                    and self.validate_path(): return True
        # HTTP/0.9
        elif len(status_line) == 2:
            self.__version = 'HTTP/0.9'
            self.__method, self.__path = status_line
            if self.__method == 'GET' and self.validate_path(): \
                    return True
            self.__version = self.version
            self.send_error(400)
        # Bad request
        else:
            # Reset protocol version
            self.__version = self.version
            self.send_error(400)
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
        if path == '' or path == ' ' or not path.startswith("/"): return False
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
        #print(self.__query_string)
        path = path[0]
        path = os.path.abspath(path)
        path = self.server.PUBLIC_DIR + path
        #print(path)
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
        connection = ''
        for line in self.__headers:
            #print(line)
            try:
                f, v = [x.strip() for x in line.split(':',1)]
                if f.lower() == 'connection':
                    if v.lower() == 'close':
                        connection = v.lower()
                    elif v.lower() == 'keep-alive': 
                        connection = v.lower()
                        #self.add_header("Connection","close")
                elif f.lower() == 'content-length': self.__content_length = v
                elif f.lower() == 'content-type': self.__content_type = v
            except:
                # XXX: Should handle this
                pass
        # Check if connection header was set
        #print(connection)
        if len(connection) > 0:
            if connection == 'close': self.close = True
            else: self.close = False
        else:
            if self.__version == 'HTTP/0.9' or self.__version == 'HTTP/1.0':
                self.close = True
            else: self.close = False # HTTP/1.1
        return True

    def send_error(self,code):
        """adds error to response queue"""
        self.add_response(code)
        if self.__version != 'HTTP/0.9':
            if self.close: self.add_header('Connection','close')
            else: self.add_header('Connection','keep-alive')
            self.add_header('Content-Length','0')
        self.add_end_header()
        self.queue_response()
        # TODO: Add message boyd
    
    def queue_response(self):
        """adds current response to response queue and resets current vars"""
        self.response_queue.put(self.__response)
        self.refresh()
    
    def queue_file(self):
        """adds a file to response queue"""
        try:
            with open(self.__path,'rb') as f:
                self.add_response(200,'OK')
                if self.__version != 'HTTP/0.9':
                    size, mtime = self.get_file_info(f)
                    self.add_header('Content-Length',str(size))
                    if self.close: self.add_header('Connection','close')
                    else: self.add_header('Connection','keep-alive')
                    self.add_header('Content-Type',self.get_file_type(self.__path))
                self.add_end_header()
                self.__response += f.read()
                self.queue_response()
        except IOError as e:
            self.send_error(500)

    def add_response(self, code, message = None):
        """writes response status code and default headers"""
        # Validate code
        if not isinstance(code, int): raise TypeError("\'{0}\' is not an integer. Must be an integer i.e. 200 or \'200\'".format(code))
        self.code = code
        if code < 100 or code > 599: raise ValueError("\'{0}\' is invalid value. Must be in range [100,600)")
        if not message:
            try:
                message = self.__responses[code]
            except KeyError:
                message = '???'
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
        self.__response += '{0}: {1}'.format(
                name.strip(),value.strip()).encode()
        self.add_end_header()
    
    def add_end_header(self):
        self.__response += self.__lt.encode()

    def server_string(self):
        """returns server name and version"""
        return __servername__ + '/' + __version__
    
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

    
    # TODO: ------------------ NEEDS WORK BElOW -------------------------------
    # _________________________________________________________________________
    # _________________________________________________________________________
    # _________________________________________________________________________
    # _________________________________________________________________________
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
    
    def get_file_info(self, f):
        fs = os.fstat(f.fileno())
        size = fs.st_size
        mtime = fs.st_mtime
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

    def __init__(self, config_filename = "config"):

        # Reading settings from config file
        # CAUTION path/filename?
        self.configure(config_filename)
        # Setting up the HTTP handler
        self.handler = HttpHandler
        # Set up a socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.HOST, self.PORT))
        self.socket.listen(20000) # Should be set in confing / Test it

    def configure(self, filepath):
        # Defaults:
        self.HOST = ""
        self.PORT = 8000
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
    def serve_persistent(self):
        self.conn = None
        self.connected = False
        #self.close_connection = False
        print("* Serving HTTP at port {0} (Press CTRL+C to quit)".format(self.PORT))
        signal.signal(signal.SIGCHLD, self.signal_handler)
        try:
            while True:
                if self.connected:
                    self.handler.handle()
                    self.handler.send()
                    if self.handler.close:
                        self.conn.close()
                        self.connected = False
                        del self.handler
                        os._exit(0)
                else: 
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
                        try:
                            pid = os.fork() # Needs error handling
                        except OSError as e:
                            if e.errno == errno.EINTR:
                                pid = os.fork()
                        if pid != 0: # Parent
                            # close the file descriptor
                            self.conn.close()
                        else:
                            self.socket.close()
                            self.handler = HttpHandler(self.conn,self)
                            self.connected = True
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
    def __init__(self, config = "config"):
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
                r, w, e = select.select(self.inputs, self.outputs, self.inputs)   

                # Handle inputs
                for s in r:
                    if s is self.socket:
                        # Server is ready to accept a connection
                        conn, addr = self.socket.accept()
                        # Set to non-blocking
                        conn.setblocking(False)
                        self.inputs.append(conn)
                        self.handlers[conn] = HttpHandler(conn,self)
                    else:
                        #if s not in self.handlers:
                        #    self.handlers[s] = HttpHandler(s,self)
                        handler = self.handlers[s]
                        if handler.handle():
                            if s not in self.outputs:
                                self.outputs.append(s)
                        else:
                            self.clear(s)
                            if s in w:
                                w.remove(s)
                # Handle outputs
                for s in w:
                    handler = self.handlers[s]
                    handler.send()
                    self.outputs.remove(s)
                    if handler.finished:
                        self.clear(s)
                        #self.outputs.remove(s) 
                # Handle "exceptional conditions"
                for s in e:
                    self.clear(s)
                #print (self.handlers)

        except KeyboardInterrupt:
            #print(count)
            self.clear(self.socket)

    def clear(self,connection):
        if connection in self.outputs:
            self.outputs.remove(connection)
        if connection in self.inputs:
            self.inputs.remove(connection)
        try:
            self.shutdown_connection(connection)
        except socket.error as e:
            pass
        if connection in self.handlers:
            del self.handlers[connection]

def test():
    server = ForkingServer()
    conn, _ = server.socket.accept()
    conn.setblocking(False)
    handler = HttpHandler(conn,server)
    while True:
        r,w,e = select.select([conn],[],[])
        handler.handle()
        #print (handler.response_queue.qsize())
        try:
            r = handler.response_queue.get_nowait()
        except (queue.Empty):
            pass
        except (KeyError):
            pass
        else:
            conn.send(r)
            #conn.send(r)
        if handler.close: break


if __name__ == "__main__":
    #server = ForkingServer()
    server = NonBlockingServer()
    server.serve_persistent()
