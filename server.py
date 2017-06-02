#!/usr/bin/env python
"""\
TODO: About
"""

__servername__ = "bistro"

__version__ = "0.0.2"

__all__ = ["HttpHandler", "ForkingServer", "NonBlockingServer"]

# Standard modules
import socket
import os
import subprocess
import signal
import errno
import sys
import mimetypes
import datetime
import io
# Non-blocking IO
import select
import time
from gevent.server import StreamServer
import config
import stats

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

class HttpHandler():
    """ TODO """
    # NOTE: HttpHandler is implemented as a State Machine with six stages,
    # three main stages and three sub-stages. The main stages (set below)
    # define states where we should check the buffer for data. Their use
    # is to answer the questions - Is status line recieved?, Are headers
    # recieved?, Is the body recieved? - represented by the methods -
    # status_line_recieved(), headers_recieved(), body_received(). The
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
        self._input_buffer = b''

   # Current request variables. When done, should be cleared with refresh()
    def refresh(self):
        """init and reset current request variables"""
        self._status_line = ''
        self._headers = []
        self._body = b''
        self._response = b''
        self._method = ''
        self._path = ''
        self._version = ''
        self._content_length = ''
        self._content_type = ''
        self._cgi = False
        self._stage = self.STAGE1

    # The outgoing message queue
    #response_queue = queue.Queue()
    # List of supported methods and a dictionarry of supported response codes
    _supported_methods = ['GET', 'HEAD', 'POST']
    _responses = {
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
    _lt = '\r\n'

    # Populate MIME types dictionary
    if not mimetypes.inited: mimetypes.init() # try to read system mime.types
    extensions_map = mimetypes.types_map.copy()
    extensions_map.update({
        '': 'application/octet-stream', # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        })

    def __init__(self, conn=None, addr=None, server=None, cfg=None):
        """conn stands for connection"""
        self.total_responses = 0
        self._input_buffer = b''
        self._status_line = ''
        self._headers = []
        self._body = b''
        self._response = b''
        self._method = ''
        self._path = ''
        self._version = ''
        self._content_length = ''
        self._content_type = ''
        self._cgi = False
        self._stage = self.STAGE1
        self.close = True
        self.finished = False
        self.response_queue = queue.Queue()
        if conn:
            self.conn = conn
            if addr:
                self.addr = addr
            else:
                self.addr = conn.getpeername()
        if server:
            self.server = server
        if cfg:
            self.cfg = cfg
        else:
            self.cfg = config.Config()
            self.cfg.defaults()
        if self.cfg.get('HTTP_VERSION') == 1.1: self.version = 'HTTP/1.1'
        elif self.cfg.get('HTTP_VERSION') == 1.0: self.version = 'HTTP/1.0'
        self._version = self.version
        # Create current reques variables
        self.refresh()
        # Create input buffer
        self.reset_buffer()

    def finish(self):
        self.finished = True
        self._stage = self.STAGE1
        #self.total_responses += 1

    def handle_loop(self):
        self.server.stats.add_handler(self.addr, time.time())
        while True:
            if not self.handle(): 
                self.server.stats.close(self.addr, time.time())
                return
            if self.finished:
                #self.server.stats
                #self.server.count_requests += 1
                self.send()
                if self.close:
                    self.server.stats.close(self.addr)
                    return

    #@profile
    def handle(self):
        """this class operates our state machine"""
        # Recv data from socket
        if not self.recv():
            self.close = True
            self.finish()
            # XXX: this closes the connection and does not produce a response
            # There should be a better way to account for this
            #self.total_responses -= 1
            return False
        # Check stage
        if self._stage == self.STAGE1:
            self.finished = False
            #if __debug__: print("-----STAGE 1-----")
            if self.status_line_recieved():
                #if __debug__: print("Status line received:\r\n" \
                #        + self.__status_line)
                if self.status_line_parse():
                    #if __debug__: print("Status line parsed")
                    if self._version == 'HTTP/0.9':
                        self.queue_file()
                        # XXX: The follwing call should be moved to queue_file
                        #and send_error (calle it queue_error)
                        self.finish()
                    else:
                        self._stage = self.STAGE2
                else:
                    self.finish()
                #error was sent
        if self._stage == self.STAGE2:
            #if __debug__: print("-----STAGE 2-----")
            if self.headers_recieved():
                #if __debug__: print("Headers received:\r\n" + str(self.__headers))
                if self.headers_parse():
                    if self._cgi:
                        if self._method == 'POST' and \
                                self._content_length != '' and \
                                self._content_length != '0':
                            self._stage = self.STAGE3
                        else:
                            self.queue_cgi()
                    else:
                        #if __debug__: print("Headers parsed")
                        self.queue_file()
                        #if __debug__:
                        #    print("Queued files:" + str(self.response_queue.qsize()))
                        #    print("Close:" + str(self.close))
                        #    print("Finished:" + str(self.finished))
                        self.finish()
                else:
                    self.finish()
        if self._stage == self.STAGE3:
            #if __debug__: print("------STAGE 3------")
            if self.body_received():
                #if __debug__: print("Body received:\r\n" + str(self.__body))
                self.queue_cgi()
            else:
                self.finish()
        return True

    def body_received(self):
        """"""
        try:
            print(self._content_length)
            print(self._input_buffer)
            # XXX: Better slicing?
            l = int(self._content_length)
            self._body = self._input_buffer[0:l] # XXX:l+1?
            if len(self._body) < l: raise ValueError
            self._input_buffer = self._input_buffer[l:]
            return True
        except ValueError:
            return False

    #@profile
    def recv(self):
        """returns void"""
        # Read until the socket blocks
        #if __debug__: print("Receiving..")
        while True:
            try:
                data = self.conn.recv(self.cfg.get('REQ_BUFFSIZE'))
                #if __debug__: print("Received data: \r\n{}".format(str(data)))
                # NOTE: Handles telnet termination character
                # XXX: Should probably have a mechanism inside this method  to
                # detect invalid queries if \r\n was not reached
                data = data if data != b'\xff\xf4\xff\xfd\x06' else None
                if data:
                    self._input_buffer += data
                else:
                # NOTE:client closed connection
                    self.close = True
                    return False
                if len(data) < self.cfg.get('REQ_BUFFSIZE'): break
            # Break the loop if EWOULDBLOCK
            except (socket.error, IOError) as e:
                if e.errno == errno.EINTR: continue # retry recv call
                elif e.errno != errno.EWOULDBLOCK:
                    self.close = True
                    return False# should close connection
        return True

    def send(self):
        """returns void"""
        try:
            next_response = self.response_queue.get_nowait()
        except queue.Empty:
            #if __debug__: print("Queue is empty")
            return False
        else:
            # XXX: Needs error handling
            try:
                self.conn.send(next_response)
                #if __debug__: print("{0}:{1} - - [{2}] \"{3}\" {4} -"
                #.format(self.addr[0], self.addr[1],
                #time.strftime("%d/%m/%Y %H:%M:%S", time.localtime()),
                #next_response.decode().split('\r\n',1)[0], self.code))
            except (socket.error) as e:
                print(e)
                pass
            return True

    #@profile
    def status_line_recieved(self):
        """returns True if status line was recieved"""
        try:
            self._status_line, self._input_buffer = \
                    self._input_buffer.split(self._lt.encode('utf-8'), 1)
            self._status_line = self._status_line.decode('utf-8')
            self.server.stats.add_received(self.addr)
            return True
        except ValueError:
            if len(self._input_buffer) > self.cfg.get('MAX_URL'):
                self.send_error(414)
                self.refresh()
                # NOTE: Reset input buffer
                self.reset_buffer()
            return False

    #n@profile
    def status_line_parse(self):
        """returns True if request is valid"""
        status_line = self._status_line.strip()
        status_line = status_line.split(' ')
        #print(status_line)
        # HTTP/1.0 and HTTP/1.1
        if len(status_line) == 3:
            self._method, self._path, self._version = status_line
            if self.validate_version() and self.validate_method() \
                    and self.validate_path(): return True
        # HTTP/0.9
        elif len(status_line) == 2:
            self._version = 'HTTP/0.9'
            self._method, self._path = status_line
            if self._method == 'GET' and self.validate_path(): \
                    return True
            self.send_error(400)
        # Bad request
        self.close = True
        self.send_error(400)
        return False

    #nn@profile
    def validate_version(self, version=None):
        # NOTE: Useful for unit testing later on
        if not version: version = self._version
        # XXX: Do I really need all that fuss below?
        if version[:5] != "HTTP/":
            self.send_error(400)
            return False
        try:
            version_number = version.split("/", 1)[1].split(".")
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

    #@profile
    def validate_method(self, method=None):
        if not method: method = self._method
        if method not in self._supported_methods:
            self.send_error(501)
            return False
        return True

    #@profile
    def validate_path(self, path=None):
        if not path: path = self._path
        # FIXME: Losely based on previous version - needs error handling!
        # FIXME: status_line = ['GET', ''] ?
        if path == '' or path == ' ' or not path.startswith("/"): return False
        # XXX: Check path input /cgi-bin/script.py\/
        # XXX: Is injection possible?
        # TODO: Unit tests on all methods
        # Lose parameters:
        path = path.split("#", 1)[0]
        path = path.split("?", 1)
        try:
            self._query_string = path[1]
        except:
            self._query_string = ''
        path = path[0]
        path = self.cfg.get('PUBLIC_DIR') + path
        # CGI?
        # FIXME: Replace input with configurable i.e. CGIDIR, DIRCGI, CGIPATH
        if path.startswith(self.cfg.get('CGI_DIR') + "/"):
            if self._version == 'HTTP/0.9':
                self.send_error(403)
                return False
            if os.path.isfile(path):
                self._filename = os.path.basename(path)
                self._cgi = True
                self._path = path
                return True
        # Directory?
        if os.path.isdir(path):
            for index in self.cfg.get('INDEX_FILES'):
                #index = os.path.join(path, index) #TOO SLOW
                if path.endswith("/"): index = path + index
                else: index = path + "/" + index
                if os.path.isfile(index):
                    path = index
                    break
            else:
                self.send_error(403)
                return False
        # File?
        if os.path.isfile(path):
            self._path = path
            return True
        # Strip /; check again
        path = path.rstrip("/")
        if os.path.isfile(path):
            self._path = path
            return True
        # Not found
        self.send_error(404)
        return False

    #@profile
    def headers_recieved(self):
        """returns True if headers were received"""
        # FIXME: Should validate headers, ignore bad headers, or send 400
        try:
            while True:
                header, self._input_buffer = \
                        self._input_buffer.split(self._lt.encode('utf-8'), 1)
                if not header: break
                self._headers.append(header.decode('utf-8'))
            return True
        except ValueError:
            return False
    #@profile
    def headers_parse(self):
        # XXX: Currently ignores badly formed request headers
        # FIXME: Should close connection in HTTP/1.0 unless keep-alive was
        # specified.
        connection = ''
        for line in self._headers:
            #print(line)
            try:
                f, v = [x.strip() for x in line.split(':', 1)]
                if f.lower() == 'connection':
                    if v.lower() == 'close':
                        connection = v.lower()
                    elif v.lower() == 'keep-alive':
                        connection = v.lower()
                elif f.lower() == 'content-length':
                    self._content_length = v
                elif f.lower() == 'content-type':
                    self._content_type = v
            except:
                # XXX: Should handle this
                pass
        # Check if connection header was set
        #print(connection)
        if len(connection) > 0:
            self.close = True if connection == 'close' else False
        else:
            if self._version == 'HTTP/0.9' or self._version == 'HTTP/1.0':
                self.close = True
            else: self.close = False # HTTP/1.1
        return True

    def send_error(self, code):
        """adds error to response queue"""
        self.add_response(code)
        if self._version != 'HTTP/0.9':
            if self.close: self.add_header('Connection', 'close')
            else: self.add_header('Connection', 'keep-alive')
            self.add_header('Content-Length', '0')
        self.add_end_header()
        self.queue_response()
        self.server.stats.add_error(self.addr)
        # TODO: Add message boyd

    def queue_response(self):
        """adds current response to response queue and resets current vars"""
        self.response_queue.put(self._response)
        self.refresh()
        self.finish()

    #@profile
    def queue_file(self):
        """adds a file to response queue"""
        try:
            with io.open(self._path, 'rb') as f:
                self.add_response(200, 'OK')
                if self._version != 'HTTP/0.9':
                    size, mtime = self.get_file_info(f)
                    self.add_header('Content-Length', str(size))
                    if self.close: self.add_header('Connection', 'close')
                    else: self.add_header('Connection', 'keep-alive')
                    self.add_header('Content-Type', self.get_file_type(self._path))
                self.add_end_header()
                if self._method != 'HEAD': self._response += f.read()
                self.queue_response()
                # NOTE: stats
                self.server.stats.add_success(self.addr)
        # XXX: OSError, etc.?
        except IOError as e:
            self.send_error(500)

    def add_response(self, code, message=None):
        """writes response status code and default headers"""
        # Validate code
        if not isinstance(code, int):
            raise TypeError("\'{0}\' is not an integer. \
                    Must be an integer i.e. 200 or \'200\'".format(code))
        self.code = code
        if code < 100 or code > 599:
            raise ValueError("\'{0}\' is invalid value. Must be in range [100,600)")
        if not message:
            try:
                message = self._responses[code]
            except KeyError:
                message = '???'
        if len(self._response) != 0: self.refresh() # Possibly not needed
        if self._version == 'HTTP/0.9':
            self._response += '{0} {1}\r\n'.format(code, message).encode('utf-8')
        else:
            # XXX: Should we switch versions?
            self._response += '{0} {1} {2}\r\n'\
                    .format(self.version, code, message).encode('utf-8')
            self.add_header('Date', self.date_time_string())
            self.add_header('Server', self.server_string())

    def add_header(self, name, value):
        """Writes a <name>:<value> pair to the response message"""
        # XXX: Should validate
        self._response += '{0}: {1}'\
                .format(name.strip(), value.strip()).encode('utf-8')
        self.add_end_header()

    def add_end_header(self):
        """Writes a CRLF to the response message"""
        self._response += self._lt.encode('utf-8')

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
        return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (weekday, dt.day, month,\
                dt.year, dt.hour, dt.minute, dt.second)

    def queue_cgi(self, path=None):
        """Prepares the environment and executes the CGI script defined by the path"""
        if not path: path = self._path
        env = {}
        env["SERVER_NAME"] = __servername__
        env["SERVER_SOFTWARE"] = __version__
        env["GATEWAY_INTERFACE"] = "CGI/1.1"
        env["SERVER_PROTOCOL"] = self.version
        env["SERVER_PORT"] = str(self.cfg.get('PORT'))
        env["REQUEST_METHOD"] = self._method
        env["REMOTE_ADDR"] = str(self.addr[0])
        env["REMOTE_PORT"] = str(self.addr[1])
        env["QUERY_STRING"] = self._query_string
        env["PATH_INFO"] = path
        env["SCRIPT_NAME"] = self._filename
        env["CONTENT_LENGTH"] = str(self._content_length)
        env["CONTENT_TYPE"] = self._content_type

        try:
            process = subprocess.Popen(["./" + path], stdin=subprocess.PIPE,\
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            if self._body: stdin = self._body
            else: stdin = b''
            (output, err) = process.communicate(stdin)
            exit_code = process.wait()
            if exit_code == 1 or err:
                print("ERROR calling \"{0}\":\r\n {1}".format(env["SCRIPT_NAME"],\
                        err.decode()))
                raise Exception
            self.add_response(200)
            self._response += output
            self.queue_response()
            self.server.stats.add_success(self.addr)
        except Exception:
            raise
            self.send_error(500)

    def get_file_info(self, f):
        """Returns a (size, mtype) tuple of corresponding file size and last updated timestamp"""
        fs = os.fstat(f.fileno())
        size = fs.st_size
        mtime = fs.st_mtime
        return size, mtime

    def get_file_type(self, filepath):
        """Finds the corresponsing mime type for a file, given the file path"""
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

class BaseServer(object):

    def __init__(self, config_filename="server.conf"):

        # Reading settings from config file
        # CAUTION path/filename?
        self.configure(config_filename)
        # Setting up the HTTP handler
        self.handler = HttpHandler
        # Setting up the statistics object
        self.stats = stats.RedisStats()
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
        self.INDEX_FILES = ["index.html", "index.htm"]
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
                            if key.upper() == "PORT" or key.upper() == \
                                    "REQ_BUFFSIZE": value = int(value)
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
                with io.open(filepath, "rb") as f:
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
            if self.conn: self.handler = HttpHandler(self)
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
    def __init__(self, config='server.conf'):
        super(self.__class__, self).__init__(config)
        self.conn = None
        self.addr = None
        self.connected = False
        self.stats = stats.RedisStats()

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
                        self.stats.close(self.handler.addr)
                        self.connected = False
                        del self.handler
                        os._exit(0)
                else:
                    try:
                        pair = self.socket.accept()
                    except IOError as e:
                        code, _ = e.args
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
                            self.handler = HttpHandler(self.conn, self.addr, self)
                            self.stats.add_handler(self.addr)
                            self.connected = True
        except KeyboardInterrupt:
            if self.conn: self.conn.close()
            self.socket.close()
            self.stats.print_stats()
            # TODO: Needs error handling
            #print("Total {}".format(str(self.stats.get_total())))
            #print("Times standard deviation: {}".format(self.stats.get_time_sd()))

    def signal_handler(self, signum, frame):
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except OSError:
                return
            if pid == 0:
                return


class NonBlockingServer(BaseServer):
    def __init__(self, config="server.conf"):
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
    #@profile
    def serve_persistent(self):
        print("* Serving HTTP at port {0} (Press CTRL+C to quit)".format(self.PORT))
        try:
            while self.inputs:
                # Wait for at least one socket to be ready for processing
                # Needs error handling (Keyboard Interrupt)
                r, w, e = select.select(self.inputs, self.outputs, self.inputs, 0.5)
                # Handle inputs
                for s in r:
                    if s is self.socket:
                        # Server is ready to accept a connection
                        conn, addr = self.socket.accept()
                        # Set to non-blocking
                        conn.setblocking(False)
                        self.inputs.append(conn)
                        self.handlers[conn] = HttpHandler(conn, addr, self)
                        self.stats.add_handler(addr, time.time())
                    else:
                        handler = self.handlers[s]
                        handler.handle()
                        if handler.finished:
                            if s not in self.outputs:
                                self.outputs.append(s)
                            if handler.response_queue.qsize() == 0 and \
                                    handler.close:
                                self.clear(s)
                                self.stats.close(handler.addr, time.time())
                                if s in w: w.remove(s)
                # Handle outputs
                for s in w:
                    handler = self.handlers[s]
                    if not handler.send():
                        # XXX: ?
                        self.outputs.remove(s)
                        if handler.finished and handler.close:
                            self.stats.close(handler.addr, time.time())
                            self.clear(s)
                # Handle "exceptional conditions"
                for s in e:
                    self.clear(s)
        except KeyboardInterrupt:
            self.stats.print_stats()
            self.clear(self.socket)

    def clear(self, connection):
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

class AsyncServer(StreamServer):
    def __init__(self, listener=None, **ssl_args):
        if not listener: listener = ("", 8000)
        StreamServer.__init__(self, listener, **ssl_args)
        self.max_accept = 1000  
        self.handler = HttpHandler
        self.stats = stats.RedisStats()

    #@profile
    def handle(self, socket, address):
        #self.stats.add_handler(address)
        handler = self.handler(socket, address, self)
        handler.handle_loop()
        #self.stats.close(address)
        socket.close()
        
    def serve_persistent(self):
        try:
            self.serve_forever()
        except KeyboardInterrupt:
            self.stats.print_stats()

def test():
    server = ForkingServer()
    #server = NonBlockingServer()
    #server = AsyncServer()
    server.serve_persistent()

if __name__ == "__main__":
    test()
