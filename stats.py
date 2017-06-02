"""Handler statistics"""

__all__ = ['Stats']

# Redis pubsub channel
CHANNEL = 'test'

import time
import numpy
try:
    import redis
except ModuleNotFoundError:
    pass

class Store(object):
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

    def add_handler(self, address, timestamp=None):
        """Adds a new address refference to our stats dictionary.
Timestamp should be in UTC"""
        # TODO: Should be able to cound statistics for N times that host was connected
        if not timestamp:
            timestamp = time.time()
        if address in self._statistics:
            self._statistics[address]['times_connected'] += 1
        else:
            self._statistics[address] = {'received' : 0, 'success' : 0, 'error' : 0, \
                't_opened' : timestamp, 'times_connected' : 1}
    
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

    def add_received(self, address, value=1):
        """Increments the number of received requests by value (or by default +1)"""
        self._statistics[address]['received'] += int(value)
    
    def add_success(self, address, value=1):
        """Increments the number of received requests by value (or by default +1)"""
        self._statistics[address]['success'] += int(value)
    
    def add_error(self, address, value=1):
        """Increments the number of received requests by value (or by default +1)"""
        self._statistics[address]['error'] += int(value)
    
    def close(self, address, timestamp=None):
        """Used to set the time when the connection is closed.
Timestamp should be in UTC"""
        if not timestamp:
            timestamp = time.time()
        self._statistics[address]['t_closed'] = timestamp

    def open(self, address, timestamp=None):
        """Used to set the time when the connection is first opened.
Timestamp should be in UTC"""
        if not timestamp:
            timestamp = time.time()
        self._statistics[address]['t_opened'] = timestamp

    def get_all_dtime(self):
        times = []
        for key in self._statistics:
            try:
                d_time = self._statistics[key]['t_closed'] - \
                    self._statistics[key]['t_opened']
            except KeyError:
                return None
            times.append(d_time)
        return times
    
    def get_all_open(self):
        times = []
        for key in self._statistics:
            try:
                time = self._statistics[key]['t_opened']
            except KeyError:
                return None
            times.append(time)
        return times

    def get_all_close(self):
        times = []
        for key in self._statistics:
            try:
                time = self._statistics[key]['t_closed']
            except KeyError:
                return None
            times.append(time)
        return times

    def get_all_recv(self):
        received = []
        for key in self._statistics:
            n_recv = self._statistics[key]['received']
            received.append(n_recv)
        return received
            

    def print_stats(self):
        # Arrays
        d_times = self.get_all_dtime()
        o_times = self.get_all_open()
        c_times = self.get_all_close()
        n_recv = self.get_all_recv()
        # Standard Deviation
        dtime_sd = numpy.std(d_times, dtype=numpy.float64)
        time_sd = numpy.std(o_times, dtype=numpy.float64)
        close_sd = numpy.std(c_times, dtype=numpy.float64)
        n_recv_sd = numpy.std(n_recv, dtype=numpy.float64)
        #
        fo = min(o_times)
        lo = max(o_times)
        fc = min(c_times)
        lc = max(c_times)
        d_lc_fo = lc - fo
        d_lo_fo = lo - fo
        d_lc_fc = lc - fc
        print("Delta Time Standard Deviatioin: {}".format(dtime_sd))
        print("Delta Last Closed - First Opened: {}".format(d_lc_fo))
        print("Delta Last Opened - First Opened: {}".format(d_lo_fo))
        print("Delta Last Closed - First Closed: {}".format(d_lc_fc))
        print("Open Time Standard Deviation: {}".format(time_sd))
        print("Close Times Standard Deviation: {}".format(close_sd))    
        print("Received Requests Standard Deviation: {}".format(n_recv_sd))

class RedisMixIn:
    r = redis.Redis()
    
    def reset(self):
        """Resets the Stats object. WARNING: Deletes all values"""
        self.r.publish(CHANNEL, 'reset()')
    
    def get_total(self):
        """Used to retrieve a total for all of the handlers"""
        self.r.publish(CHANNEL, 'get_total()') 

    def add_handler(self, address, timestamp=None):
        """Adds a new address refference to our stats dictionary.
Timestamp should be in UTC"""
        self.r.publish(CHANNEL, 'add_handler("' + str(address) + '")')

    def get_handler(self, address, stat=None):
        """Used to retreive the stats for a particular handler.
Can also retrieve a single stat if parameter stat was set"""
        self.r.publish(CHANNEL, 'get_handler("' + str(address) + '")')

    def get_all(self):
        """Used to retrive the statistics dictionary"""
        self.r.publish(CHANNEL, 'get_all()')

    def add_received(self, address, value=1):
        """Increments the number of received requests by value (or by default +1)"""
        self.r.publish(CHANNEL, 'add_received("' + str(address) + '",' + str(value) + ')')
    
    def add_success(self, address, value=1):
        """Increments the number of received requests by value (or by default +1)"""
        self.r.publish(CHANNEL, 'add_received("' + str(address) + '",' + str(value) + ')')
    
    def add_error(self, address, value=1):
        """Increments the number of received requests by value (or by default +1)"""
        self.r.publish(CHANNEL, 'add_received("' + str(address) + '",' + str(value) + ')')
    
    def close(self, address, timestamp=None):
        """Used to set the time when the connection is closed.
Timestamp should be in UTC"""
        self.r.publish(CHANNEL, 'close("' + str(address) + '")')

    def open(self, address, timestamp=None):
        """Used to set the time when the connection is first opened.
Timestamp should be in UTC"""
        self.r.publish(CHANNEL, 'open("' + str(address) + '")')
    
    def get_all_dtime(self):
        self.r.publish(CHANNEL, 'get_all_dtime()')

    def get_all_open(self):
        self.r.publish(CHANNEL, 'get_all_open()')

    def get_all_close(self):
        self.r.publish(CHANNEL, 'get_all_close()')

    def get_all_recv(self):
        self.r.publish(CHANNEL, 'get_all_recv()')            

    def print_stats(self):
        self.r.publish(CHANNEL, 'print_stats()')

class RedisStore(RedisMixIn, Store): pass

def test():
    s = Stats()
    s.add_handler('a')
    s.inc_success('a',1)
    s.inc_error('a',12)
    s.add_handler('b')
    s.inc_received('b',10)
    al = s.get_handler('a')
    print(s.get_total())

def test2():
    s = RedisStats()
    s.add_handler('a')

if __name__ == "__main__":
    test2()
