#!/usr/bin/env python
lt="\r\n"
print("Content-Type: text/html",end=lt)
print(end=lt)

print("<title>CGI script output</title>",end=lt)
print("<h1> This is a sample CGI script</h1>",end=lt)
print("Hellow, world!",end=lt)
print("<ul>",end='')
for i in range(0,20):
    print("<li>" + str(i) +"</li>",end='')
print("</ul>",end=lt)
