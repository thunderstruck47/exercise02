#!/usr/bin/env python
import os
import sys

# Prepare response body
body = "<title>CGI script output</title>\r\nThis is a sample CGI script</h1>\r\nHellow, world!\r\n"
body += "<ul>\r\n"
for i in range(0,20):
    body += "<li>" + str(i) +"</li>\r\n"
body += "</ul>\r\n"
body += "<p>" + str(os.environ.copy()) + "</p>\r\n"

# Read and add request body to response body
if os.environ["REQUEST_METHOD"]=="POST" and os.environ["CONTENT_LENGTH"]!="0" and os.environ["CONTENT_LENGTH"]!="" :body += "<p>" + sys.stdin.read() + "</p>\r\n"

# Calculate the size of the response
size = len(body.encode('utf-8')) + 1 # +1, else chrome interrupts connection

# Response:
print("Content-Type: text/html",end = "\r\n")
print("Content-Length: {0}".format(size))
print(end = "\r\n")
print(body)


