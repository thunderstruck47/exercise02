#!/usr/bin/env python
import fileinput
import os

body = "<title>CGI script output</title>\r\nThis is a sample CGI script</h1>\r\nHellow, world!\r\n"
body += "<ul>\r\n"
for i in range(0,20):
    body += "<li>" + str(i) +"</li>\r\n"
body += "</ul>\r\n"
body += "<p>" + str(os.environ.copy()) + "</p>\r\n"
if os.environ["REQUEST_METHOD"]=="POST" and os.environ["CONTENT_LENGTH"]!="0": body += "<p>" +fileinput.input()[0]+ "</p>\r\n"

size = len(body.encode('utf-8'))

print("Content-Type: text/html",end = "\r\n")
print("Content-Length: {0}".format(size))
print(end = "\r\n")
print(body)


