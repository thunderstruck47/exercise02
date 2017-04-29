# Web Server

A very simple HTTP static file server

### Dependencies

Compatible with GNU/Linux and UNIX systems

Currently works with a Python 2.7 interpreter, with Python 3 version on it's way..

Requires (optionally) [python-magic](https://github.com/ahupp/python-magic) module for advanced file type identification

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
* Testing