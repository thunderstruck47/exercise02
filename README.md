# Web Server

A very simple HTTP static file server

## Dependencies

Needs a Python 2.7 interpreter

## Features

* Basic configuration
* Serve static files
* Persistent, non persistent and single connections
* Handle concurrent requests via forking
* Supports HTTP GET, HEAD and POST(currently replicates GET, parameters ignored)
* Currently implemented HTTP/1.0

## Configuration

Example configuration file

````
[server]
host = localhost
port = 8000
public_dir = www
request_buffsize = 4096
index_files = index.html index.htm
````
