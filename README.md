# Web Server

A very simple HTTP static file server

### Dependencies

Currently compatible with GNU/Linux and UNIX systems. Needs a Python 2 interpreter (soon to be working with Python 3). Optionally, requires [python-magic](https://github.com/ahupp/python-magic) module for advanced file type identification

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
* Supports GET, HEAD and POST(ignores parameters) for HTTP/1.0 and HTTP/1.1
* Servers static files only (no WSGI)
* Basic server configuration via file
* Handles persistent, non persistent and single connections
* Handles concurrent requests via forking

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
* Directory file listing page
* Proper documentation
* Proper logging
* Automated tests