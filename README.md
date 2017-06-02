# Web Server

A very simple HTTP static file server

### Dependencies

Currently compatible with GNU/Linux and UNIX systems. Works with Python 2.7 and Python 3.x interpreters. Optionally but recommended, requires [python-magic](https://github.com/ahupp/python-magic) module for advanced file type identification

### Installation and Start-up

Get the code, edit the server.conf file (you can use the example config below) and start the server. I.e.
````
git clone https://github.com/thunderstruck47/exercise02.git
cd exercise02
python server.py
````

### Features

* Speaks (partially) HTTP/0.9, HTTP/1.0 and HTTP/1.1
* Supports GET, HEAD and POST methods
* Basic server configuration via config file (server.conf by default)
* Handles persistent, non persistent and single connections
* Handles concurrency via forking, non-blocking IO and asynchronously
* Serves static files of various MIME types
* Basic CGI script handling (scripts must set "content-length" and "content-type")

### Configuration

Example configuration file

````
[server]
host = localhost
port = 8000
public_dir = www
cgi_dir = www/cgi-bin
req_buffsize = 4096
index_files = index.html index.htm
````

### To do

* ~~Handle zombie processes~~
* ~~HTTP/1.1 and HTTP/0.9 support~~
* ~~Basic CGI handling~~
* ~~Non-blocking IO (select)~~
* ~~Async (with gevent)~~
* Statistics collector
* Monitoring shell

# Optional
* Support for multiple transfer encodings
* Support for multiple charsets
* Caching
* [5%]Documentation
* [5%]Testing
