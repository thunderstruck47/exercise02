import redis
import stats
import time
from multiprocessing import Process

class Monitor(object):
    def __init__(self, r, channels):
        self.redis = r
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(channels)
        self.stats = stats.Stats()
    
    def work(self, item):
        data = item['data'].decode()
        result = eval('self.stats.' + data)

    def run(self):
        while True:
            for item in self.pubsub.listen():
                #print(item)
                if item['data'] == 1: pass
                elif item['data'] == "KILL":
                    print(self, "unsubscribed and finished")
                else:
                    self.work(item)

if __name__ == "__main__":
    r = redis.Redis()
    m = Monitor(r,["test"])
    m.run()
