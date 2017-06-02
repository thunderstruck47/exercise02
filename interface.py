"""A file containing all of our interfaces.
Currently contains only Stats interface
"""
from redis import Redis
import time

__all__ = ['Stats']

class Stats(object):
    """Stats interface"""
    r = Redis()
    # Default channel:
    _c = 'statistics'

    @classmethod
    def set_count(self, addr, op, value=1):
        """Publishes a message containg issuers' address, increase operation and value.
:addr -> string1
:op -> string, either 'recv', 'success' or 'error'
:value -> int,string, either int, '+' or '-'
"""
        ops = ['recv', 'success', 'error']
        if op not in ops: raise ValueError('Invalid value for parameter :op')
        if value == "+": value = 1
        elif value == "-": value = -1
        assert isinstance(value, int), 'parameter :value must be integer'
        self._publish(addr, op, value)

    @classmethod
    def set_time(self, addr, op, time=None):
        """Publishes a message containg issuers' address, time operation and timestamp.
:addr -> string1
:op -> string, either 'recv', 'success' or 'error'
:time -> float, should be time.time()
"""
        ops = ['t_open','t_close']
        if op not in ops: raise ValueError('Invalid value for parameter :op')
        if not time: time = time.time()
        else: assert isinstance(time, float), 'parameter :time must be float'
        self._publish(addr, op, time)

    @classmethod
    def _publish(self, addr, op, value):
        """Helper method to prepare and publish the message"""
        msg = "{} {} {}".format(str(addr), op, value)
        self.r.publish(self._c, msg)

    @classmethod
    def set_channel(self, channel):
        """Sets the class channel for statistics"""
        assert isinstance(channel, str), ':channel should be a string'
        channel.strip()
        if len(channel.split()) > 1: raise ValueError('Invalid value for :channel')
        self._c = channel

    @classmethod
    def get_channel(self):
        """Used to retreive current class channel"""
        return self._c
