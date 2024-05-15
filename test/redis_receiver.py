import time
import json

r = redis.Redis(host='localhost', port=6379)

while True:
    key = r.rpop('queue')
    if key is None or not key:
        time.sleep(1)
        continue

    decoded_key = key.decode('utf-8')
    # value = r.get(decoded_key)
    print(decoded_key)

    json_key = json.loads(decoded_key)
    print(json_key)
    break
