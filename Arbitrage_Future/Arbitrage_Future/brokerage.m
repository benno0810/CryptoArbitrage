thres = 100
sell_x = 10:0.1:200
sell_y = (sell_x/thres).^-1*30
sell_y(sell_x>thres)=sell_y(sell_x==thres)
plot(sell_x,sell_y)