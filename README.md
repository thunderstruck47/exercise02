# Web Server

A very simple HTTP static file server

### Dependencies

Needs a Python 2.7 interpreter

### Features

* Basic configuration
* Serves static files
* Persistent, non persistent and single connections
* Handles concurrent requests via forking
* Supports HTTP GET, HEAD and POST(works the same as GET; parameters are ignored)
* Currently speaks only HTTP/1.0

### Configuration

Example configuration file

````
[server]
host = localhost
port = 8000
public_dir = www
request_buffsize = 4096
index_files = index.html index.htm
````

### To do

* Handle ghost child processes
* Implement HTTP/1.1 and HTTP/0.9 support
* List directory page
* Proper documentation
