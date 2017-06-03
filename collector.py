from redis import Redis
from stats import Store
from threading import Thread

class Collector(Thread):
    def __init__(self, r, channels):
        Thread.__init__(self)
        self.redis = r
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(channels)
        self.stats = Store()
    
    def work(self, item):
        data = item['data'].decode()
        #print(data.rsplit(' ', 2))
        print(data)
        #result = eval('self.stats.' + data)

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
    r = Redis()
    c = Collector(r,['statistics'])
    c.start()
