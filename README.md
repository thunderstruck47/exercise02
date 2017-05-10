# Web Server

A very simple HTTP static file server

### Dependencies

Currently compatible with GNU/Linux and UNIX systems. Works with Python 2.7 and Python 3.x interpreters. Optionally but recommended, requires [python-magic](https://github.com/ahupp/python-magic) module for advanced file type identification

### Installation and Start-up

Get the code, edit the server.conf file (you can use the example config below) and start the server. I.e.
````
git clone https://github.com/thunderstruck47/exercise02.git
cd exercise02
vim server.conf
python2 server.py
````

### Features

* Speaks (partially) HTTP/0.9, HTTP/1.0 and HTTP/1.1
* Supports GET, HEAD and POST methods
* Basic server configuration via file
* Handles persistent, non persistent and single connections
* Handles concurrency via forking
* Serves static files
* Basic CGI handling ("www/cgi-bin" folder)

### Configuration

Example configuration file

````
[server]
host = localhost
port = 8000
public_dir = www
req_buffsize = 4096
index_files = index.html index.htm
````

### To do

* ~~Handle defunct child processes~~
* ~~HTTP/1.1 and HTTP/0.9 support~~
* ~~CGI-compatible~~
* Non-blocking version (using select)
* Async version
* Directory file listing page
* Proper documentation
* Proper logging
* Automated tests
