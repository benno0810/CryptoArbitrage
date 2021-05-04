import json
r = json.load(open('1.json','r'))
if r['polo_type'] == "buy":
    print "polo_btc_decrease",float(r['polo_amount'])*float(r['polo_price'])
    print "polo_eth_increase",float(r["polo_amount"])*0.9975
    print "btc_buy",float(r['polo_amount'])*float(r['polo_price'])/0.998
    print "eth_sell",float(r["polo_amount"])*0.9975
    print "money",float(r["polo_amount"])*0.9975*float(r["eth_price"])-float(r['polo_amount'])*float(r['polo_price'])/0.998*float(r["btc_price"])
    print 0.4*2429

