import json
s = open('status.json','r')
s = json.load(s)
num =0
mm = 0
for t in s['current_future']:
    num+=t['current']['amount']
    mm+=t['current']['money']
print mm
print num

