import asyncio
import threading
import time
import os
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors
from matplotlib.ticker import PercentFormatter
import plotly.plotly as py
import pandas as pd
from dquant.scripts.basic_units import cm, inch
import copy

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
rootPath = os.path.split(rootPath)[0]
os.sys.path.append(rootPath)


def get_one_city_data(filename):
    city = filename.split('.')[0].split('_')[-1]

    data = []
    with open(filename) as f:
        for line in f.readlines():
            data.append(line.strip().split(':'))

    dic = {}
    for one in data:

        #one[0]是market
        if one[0] not in dic:
            dic[one[0]] = {}
            dic[one[0]][city] = {}

        # one[1]是api
        if one[1] not in dic[one[0]][city]:
            dic[one[0]][city][one[1]] = {}


        # (0, 10) (10, 20), (20, 30), (30, 40), (40, 无穷大)
        if float(one[2]) < 10:
            if 0 in dic[one[0]][city][one[1]]:
                dic[one[0]][city][one[1]][0] += 1
            else:
                dic[one[0]][city][one[1]][0] = 1
        elif float(one[2]) < 20:
            if 1 in dic[one[0]][city][one[1]]:
                dic[one[0]][city][one[1]][1] += 1
            else:
                dic[one[0]][city][one[1]][1] = 1
        elif float(one[2]) < 30:
            if 2 in dic[one[0]][city][one[1]]:
                dic[one[0]][city][one[1]][2] += 1
            else:
                dic[one[0]][city][one[1]][2] = 1
        elif float(one[2]) < 40:
            if 3 in dic[one[0]][city][one[1]]:
                dic[one[0]][city][one[1]][3] += 1
            else:
                dic[one[0]][city][one[1]][3] = 1
        else:
            if 4 in dic[one[0]][city][one[1]]:
                dic[one[0]][city][one[1]][4] += 1
            else:
                dic[one[0]][city][one[1]][4] = 1

    return dic, city


def format_data(file1, file2, file3):

    dic1, city1 = get_one_city_data(file1)
    dic2, city2 = get_one_city_data(file2)
    dic3, city3 = get_one_city_data(file3)


    dic_bfx = {}
    dic_bfx['bfx'] = {}
    dic_bfx['bfx'][city1] = dic1['Bitfinex'][city1]
    dic_bfx['bfx'][city2] = dic2['Bitfinex'][city2]
    dic_bfx['bfx'][city3] = dic3['Bitfinex'][city3]

    dic_ok = {}
    dic_ok['ok'] = {}
    dic_ok['ok'][city1] = dic1['OKEX'][city1]
    dic_ok['ok'][city2] = dic2['OKEX'][city2]
    dic_ok['ok'][city3] = dic3['OKEX'][city3]

    dic_bi = {}
    dic_bi['bi'] = {}
    dic_bi['bi'][city1] = dic1['Binance'][city1]
    dic_bi['bi'][city2] = dic2['Binance'][city2]
    dic_bi['bi'][city3] = dic3['Binance'][city3]

    dic_hb = {}
    dic_hb['hb'] = {}
    dic_hb['hb'][city1] = dic1['HuoBiPro'][city1]
    dic_hb['hb'][city2] = dic2['HuoBiPro'][city2]
    dic_hb['hb'][city3] = dic3['HuoBiPro'][city3]

    dic_bfx_new = count_cnt(dic_bfx)
    dic_ok_new = count_cnt(dic_ok)
    dic_bi_new = count_cnt(dic_bi)
    dic_hb_new = count_cnt(dic_hb)

    print(dic_bfx_new)
    print(dic_ok_new)
    print(dic_bi_new)
    print(dic_hb_new)

    return dic_bfx_new, dic_ok_new, dic_bi_new, dic_hb_new


def count_cnt(dic):
    dic_new = copy.deepcopy(dic)
    for mkt, item in dic_new.items():
        for city, apis in item.items():
            for api, v in apis.items():
                tmp = []
                for one in range(5):
                    if one in v:
                        tmp.append(v[one])
                    else:
                        tmp.append(0)
                dic_new[mkt][city][api] = tmp
    return dic_new


def draw(file1, file2, file3, city1, city2, city3):
    dic_bfx, dic_ok, dic_bi, dic_hb = format_data(file1, file2, file3)


    unit_subplot(dic_bfx, 'bfx', city1, city2, city3)
    unit_subplot(dic_ok, 'ok', city1, city2, city3)
    unit_subplot(dic_bi, 'bi', city1, city2, city3)
    unit_subplot(dic_hb, 'hb', city1, city2, city3)


#def unit_subplot(m1, m2, m3, m4, m5, m6, m7, m8, m9, market):
def unit_subplot(dic, market, city1, city2, city3):

    m1 = dic[market][city1]['get_account']
    m2 = dic[market][city2]['buy']
    m3 = dic[market][city3].get('cancel', [0,0,0,0,0])

    m4 = dic[market][city1]['get_account']
    m5 = dic[market][city2]['buy']
    m6 = dic[market][city3].get('cancel', [0,0,0,0,0])

    m7 = dic[market][city1]['get_account']
    m8 = dic[market][city2]['buy']
    m9 = dic[market][city3].get('cancel', [0,0,0,0,0])

    x = [0, 1, 2, 3, 4]

    f, ((ax1, ax2, ax3), (ax4, ax5, ax6), (ax7, ax8, ax9)) = plt.subplots(3, 3, sharex='col', sharey='row')

    ax1.bar(x, m1, 0.2)
    ax1.set_title('{} get_account'.format(market))
    ax1.set_ylabel(city1)

    ax2.bar(x, m2, 0.2)
    ax2.set_title('{} buy'.format(market))


    ax3.bar(x, m3, 0.2)
    ax3.set_title('{} cancel'.format(market))


    ax4.bar(x, m4, 0.2)
    ax4.set_ylabel(city2)

    ax5.bar(x, m5, 0.2)
    ax6.bar(x, m6, 0.2)
    ax7.bar(x, m7, 0.2)
    ax7.set_ylabel(city3)

    ax8.bar(x, m8, 0.2)
    ax9.bar(x, m9, 0.2)
    ax8.set_xlabel('unit: 10ms')

    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    draw('performance_get_account_hkb.log', 'performance_get_account_hkc.log', 'performance_get_account_tokyo.log', 'hkb', 'hkc', 'tokyo')

    #get_one_city_data('performance_get_account_mengmai.log')
    #format_data('performance_get_account_mengmai.log', 'performance_get_account_shouer.log', 'performance_get_account_tokyo.log')
    #test_plot()

    ''' 
    m1 =  (1, 12, 1, 11,1)
    m2 =  (21, 21, 20, 22,1)
    m3 = (29, 27, 28, 24,1)
    m4 = (41, 39, 35, 37,1)
    m5 = (10, 12, 10, 11,1)
    m6 = (21, 21, 20, 22,1)
    m7 = (29, 27, 28, 24,1)
    m8 = (41, 39, 35, 37,1)
    m9 = (10, 12, 10, 11,1)
    unit_subplot(m1, m2, m3, m4, m5, m6, m7, m8, m9)
    '''