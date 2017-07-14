#!/usr/bin/env python
import cmd

class Shell(cmd.Cmd):
    """Interactive Monitor Shell"""
    def do_greet(self, line):
        print('hello')

    def do_exit(self, line):
        """Documentation"""
        return True

if __name__ == '__main__':
    Shell().cmdloop()
