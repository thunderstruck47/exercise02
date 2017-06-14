from redis import Redis
from redis.exceptions import ConnectionError
from stats import Store
from threading import Thread
import sys

class Collector(Thread):
    def __init__(self, r, channels):
        Thread.__init__(self)
        self.redis = r
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(channels)
        self.stats = Store()

    def shell(self):
        while True:
            line = sys.stdin.readline()
            line = line.strip()
            if line == 'print':
                try:
                    self.stats.print_stats()
                except ValueError:
                    print("Not enough data")

    def work(self, item):
        data = item['data'].decode()
        # XXX: Needs message validation!
        data = data.rsplit(' ', 2)
        params = dict(zip(['addr','op','data'], data))
        print(params) # Prits out the received message
        # Choose operation (similar to C switch statement)
        # Default is None
        op = {
            'register': self.stats.add_handler,
            'recv': self.stats.add_received,
            'success': self.stats.add_success,
            'error': self.stats.add_error,
            't_close': self.stats.close,
            't_open': self.stats.open }.get(params['op'], None)
        # Execute operation with given parameters
        if op:
            try:
                op(params['addr'], params['data'])
            except (KeyError, ValueError):
                print("Invalid data")
        else:
            print("Invalid operation")

    def run(self):
        for item in self.pubsub.listen():
            #print(item)
            if item['data'] == 1: pass
            elif item['data'] == "KILL":
                print(self, "unsubscribed and finished")
                break
            else:
                self.work(item)

if __name__ == '__main__':
    try:
        r = Redis()
        c = Collector(r,['statistics'])
        c.start()
        c.shell()
    except ConnectionError:
        print("Could not connect to redis. Redis needs to be started before collector")
    
