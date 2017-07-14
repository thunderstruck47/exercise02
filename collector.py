from redis import Redis
from redis.exceptions import ConnectionError
from stats import Store
from threading import Thread
from os import path
import sys
import pickle
if sys.version[0] == '2': 
    input = raw_input

class Collector(Thread):
    def __init__(self, r, channels):
        Thread.__init__(self)
        self.redis = r
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(channels)
        self.stats = Store()

    def shell(self):
        help_str = """\
This shell accepts the following commands:
    help, ?         - display this message
    print           - get current statistics
    total           - get total statistics
    save <filename> - save Store object to file
    load <filename> - loads Store object from file
    reset, clear    - clears current Store object
    exit, quit      - quit the interactive shell\
"""
        while True:
            sys.stdout.write('>> ')
            sys.stdout.flush()
            line = sys.stdin.readline()
            line = line.strip()
            if line.upper() in ['EXIT', 'QUIT']:
                sys.exit()
            elif line.upper() in ['HELP','?']:
                print(help_str)
            elif line.upper() == 'PRINT':
                try:
                    self.stats.print_stats()
                except ValueError:
                    print("Not enough data")
            elif line.upper() in ['RESET', 'CLEAR']:
                self.stats.reset()
            elif line.upper() == 'TOTAL':
                print(self.stats.get_total())
            else:
                line = line.split(' ', 1)
                op = line[0]
                try:
                    filename = line[1]
                except IndexError:
                    if op.upper() in ['SAVE', 'LOAD']:
                        print("You need to specify a filename to {}".format(op.lower()))
                        continue
                if op.upper() == 'SAVE':
                    self.stats.save(path.normpath(filename))
                elif op.upper() == 'LOAD':
                    if self.stats.get_total()['handlers'] > 0:
                        ans = input("Any current statistics will be lost. Are you sure? (Y/n): ")
                    else:
                        ans = 'Y'
                    if ans.upper() == 'Y' or ans.upper() == 'YES':
                        try:
                            fh = open(path.normpath(filename), 'rb')
                        except FileNotFoundError:
                            print("File not found!".format(filename))
                            continue
                        self.stats = pickle.load(fh)
                else:
                    print("Invalid command '{}'".format(op))
                    print(help_str)

    def work(self, item):
        data = item['data'].decode()
        # XXX: Needs message validation!
        data = data.rsplit(' ', 2)
        params = dict(zip(['addr','op','data'], data))
        #print(params) # Prits out the received message
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
    
