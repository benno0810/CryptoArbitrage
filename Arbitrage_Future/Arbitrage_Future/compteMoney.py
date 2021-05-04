import json

js = json.load(open("tmp.json","r"))
eth = 20
btc = 5
# 20.00099600
# 4.99987991

for l in js:
    if l['type']=='buy':
        btc-=float(l['total'])
        eth+=float(l['amount'])*(1-float(l['fee']))
    else:
        btc+=float(l['total'])*(1-float(l['fee']))
        eth-=float(l['amount'])
print btc,eth
print js
