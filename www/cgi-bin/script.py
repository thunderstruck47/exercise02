#!/usr/bin/env python
import os
import sys

# Prepare response body
body = "<title>CGI script output</title>\r\n<h1>This is a sample CGI script</h1>\r\nHellow, world!\r\n"
body += "<ul>\r\n"
for i in range(0,20):
    body += "<li>" + str(i) +"</li>\r\n"
body += "</ul>\r\n"
body += "<h3>Environmental variables:</h3><p>" + str(os.environ.copy()) + "</p>\r\n"

params = os.environ["QUERY_STRING"].split("&")
if len(params)>1:
    body += "<h1>"
    for each in params:
        body += " "+each+" "
    body +="</h1>"

# Read and add request body to response body
if os.environ["REQUEST_METHOD"]=="POST" and os.environ["CONTENT_LENGTH"]!="0" and os.environ["CONTENT_LENGTH"]!="" :
    body += "<h3>Request body:</h3><p>" + sys.stdin.read() + "</p>\r\n"

# Calculate the size of the response
size = len(body) + 1 # +1, else chrome interrupts connection

# Response:
print("Content-Type: text/html",end = "\r\n")
print("Content-Length: {0}".format(size))
print(end = "\r\n")
print(body)


