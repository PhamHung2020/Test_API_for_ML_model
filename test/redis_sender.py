import redis
import json

r = redis.Redis(host='localhost', port=6379)

data = {
    'id': '123',
    'filename': 'test.py',
    'path': '123456_test.py'
}

dump_data = json.dumps(data)
r.lpush('queue', dump_data)
