#!/usr/bin/env python
import unittest
import server
import socket

class UnitTest(unittest.TestCase):

    def setUp(self):
        self.server = server.NonBlockingServer()
        self.server.socket.close()
        self.server.PUBLIC_DIR = 'www'
        self.handler = server.HttpHandler(server = self.server)
    
    def test_validate_version(self):
        valid = ['HTTP/1.1', 'HTTP/1.0']
        invalid = ['', ' ', 'HTTP', 'HTTP/.0', 'HTTP/0.9', '1']
        for version in valid:
            self.assertTrue(self.handler.validate_version(version), 'version \'' + version + '\' should be valid')
        for version in invalid:
            self.assertFalse(self.handler.validate_version(version), 'version \'' + version + '\' should be invalid')
        

    def test_validate_method(self):
        for method in ['GET','POST','HEAD']:
            self.assertTrue(self.handler.validate_method(method), 'Testing with method ' + method + ': FAILED')
        for invalid_method in ['get',0.1,int,1,[],'PUT','DELETE','CONNECT','OPTIONS','TRACE','PATCH']:
            self.assertFalse(self.handler.validate_method(invalid_method), 'Testing with invalid method ' + str(invalid_method) + ': FAILED')
    
    def test_validate_path(self):
        valid_paths = ['/','/cgi-bin/script.py','/data.json/']
        invalid_paths = ['\\','/cgi-bin/','/cgi-bin','index.html','/index.tml']
        for path in valid_paths:
            self.assertTrue(self.handler.validate_path(path), 'path: ' + path + ' should be valid')
        for path in invalid_paths:
            self.assertFalse(self.handler.validate_path(path), 'path \'' + path + '\' should be invalid')
    
    def test_add_response(self):
        invalid = ['','a',None,[],['20'],'500']
        for code in invalid:
            with self.assertRaises(TypeError):
                self.handler.add_response(code)
        out_of_range = [1,99,-100,600,760]
        for code in out_of_range:
            with self.assertRaises(ValueError):
                self.handler.add_response(code)
        valid = [100,150,200,599]
        for code in valid:
            self.handler.add_response(code)
            self.assertTrue(True)

def test():
    unittest.main()

if __name__=='__main__':
    test()
