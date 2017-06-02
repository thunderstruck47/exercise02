"""Handler statistics"""

__all__ = ['Stats']

from datetime import datetime

class Stats():
    def __init__(self):
        self._statistics = {}
    
    def reset(self):
        """Resets the Stats object. WARNING: Deletes all values"""
        self._statistics = {}
    
    def get_total(self):
        """Used to retrieve a total for all of the handlers"""
        total_statistics = {'handlers':0, 'received':0, 'success':0, 'error':0}
        total_statistics['handlers'] = len(self._statistics)
        for key in self._statistics:
            total_statistics['received'] += self._statistics[key]['received']
            total_statistics['success'] += self._statistics[key]['success']
            total_statistics['error'] += self._statistics[key]['error']
        return total_statistics

    def add_handler(self, address, timestamp=datetime.utcnow()):
        """Adds a new address refference to our stats dictionary.
Timestamp should be in UTC"""
        assert address not in self._statistics, "Should handle how many times this address has connected, although ports are different"
        self._statistics[address] = {'received' : 0, 'success' : 0, 'error' : 0, \
            't_opened' : timestamp}
    
    def get_handler(self, address, stat=None):
        """Used to retreive the stats for a particular handler.
Can also retrieve a single stat if parameter stat was set"""
        if stat:
            return self._statistics[address][stat]
        else:
            return self._statistics[address]

    def get_all(self):
        """Used to retrive the statistics dictionary"""
        return self._statistics

    def inc_received(self, address, value=1):
        """Increments the number of received requests by value (or by default +1)"""
        self._statistics[address]['received'] += value
    
    def inc_success(self, address, value=1):
        """Increments the number of received requests by value (or by default +1)"""
        self._statistics[address]['success'] += value
    
    def inc_error(self, address, value=1):
        """Increments the number of received requests by value (or by default +1)"""
        self._statistics[address]['error'] += value
    
    def close(self, address, timestamp=datetime.utcnow()):
        """Used to set the time when the connection is closed.
Timestamp should be in UTC"""
        self._statistics[address]['t_closed'] = timestamp

    def open(self, address, timestamp=datetime.utcnow()):
        """Used to set the time when the connection is first opened.
Timestamp should be in UTC"""
        self._statistics[address]['t_opened'] = timestamp

def test():
    s = Stats()
    s.add_handler('a')
    s.inc_success('a',1)
    s.inc_error('a',12)
    s.add_handler('b')
    s.inc_received('b',10)
    al = s.get_handler('a')
    print(s.get_total())

if __name__ == "__main__":
    test()
