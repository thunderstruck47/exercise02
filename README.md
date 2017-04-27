# Web Server

A very simple HTTP static file server

### Dependencies

Currently works with a Python 2.7 interpreter with Python 3 version on it's way..

Requires [python-magic](https://github.com/ahupp/python-magic) community module for file type identification (based on libmagic) (should be optional)

### Features

* Basic configuration
* Serves static files
* Persistent, non persistent and single connections
* Handles concurrent requests via forking
* Supports HTTP GET, HEAD and POST(works the same as GET; parameters are ignored)
* Speaks only HTTP/1.0 (for now)

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

* Handle ghost child processes
* HTTP/1.1 and HTTP/0.9 support
* Directory file listing page
* Proper documentation
* Proper logging
