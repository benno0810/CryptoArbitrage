# -*- coding: utf8 -*-

import sys
sys.path.append('../../')
sys.path.append('../')

from dquant.common.CCPRestSDK import REST
import re


accountSid = '8a216da860bad76d0160d3ca54f20926'
accountToken = 'e992a191fec64a9482ce09cef88d75d4'
appId = '8a216da860bad76d0160d3ca554c092d'
serverIP = 'app.cloopen.com'
serverPort = '8883'
softVersion = '2013-12-26'


def sendTemplateSMS(to, datas, tempId, extend=''):
    '''
    :param to: 接收短信的人
    :param datas: 代入到{}里的值
    :param tempId: 模板id
    :param extend:
    :return:
    '''
    # 检查是否为+86 xxxxxxxxxxx，去掉+86
    if re.match('^\+86', to):
        to = to[3:]

    rest = REST(serverIP, serverPort, softVersion)
    rest.setAccount(accountSid, accountToken)
    rest.setAppId(appId)

    try:
        result = rest.sendTemplateSMS(to, datas, tempId)
        print(result, type(result))
    except Exception as e:
        print(e)
        return -1

    rsp = {}
    for k, v in result.items():
        if k == 'templateSMS':
            for k, s in v.items():
                rsp[k] = s
                # print '%s:%s' % (k, s)
        else:
            rsp[k] = v
            # print '%s:%s' % (k.encode('utf-8'), v.encode('utf-8'))
            # logger.debug('%s:%s' % (k.encode('utf-8'), v.encode('utf-8')))
    # print rsp['statusCode']
    print(rsp,type(rsp))
    if rsp['statusCode'] != '000000':
        return -1
    else:
        print('yuntongxun: send sms to %s successfully.' % to)
        return 0


def query_sms_templates():
    rest = REST(serverIP, serverPort, softVersion)
    rest.setAccount(accountSid, accountToken)
    rest.setAppId(appId)

    try:
        result = rest.QuerySMSTemplate("")
        return result
    except Exception as e:
        print(e)
        return -1


def check_account():
    rest = REST(serverIP, serverPort, softVersion)
    rest.setAccount(accountSid, accountToken)
    rest.setAppId(appId)

    try:
        result = rest.queryAccountInfo()
        return result
    except Exception as e:
        print(e)
        return -1


def landingCall(to, mediaName, mediaTxt, displayNum, playTimes, respUrl, userData, maxCallTime, speed, volume, pitch, bgsound):
    #初始化REST SDK
    rest = REST(serverIP,serverPort,softVersion)
    rest.setAccount(accountSid, accountToken)
    rest.setAppId(appId)

    result = rest.landingCall(to, mediaName, mediaTxt, displayNum, playTimes, respUrl, userData, maxCallTime, speed, volume, pitch, bgsound)
    for k, v in result.iteritems():
        if k == 'LandingCall':
            for k, s in v.iteritems():
                print('%s:%s' % (k, s))
        else:
            print('%s:%s' % (k, v))


def MediaFileUpload(filename, path):
    #初始化REST SDK
    rest = REST(serverIP, serverPort, softVersion)
    rest.setAccount(accountSid, accountToken)
    rest.setAppId(appId)

    file_object = open(path, 'rb')
    try:
        body = file_object.read()
    finally:
        file_object.close()

    result = rest.MediaFileUpload(filename, body)
    for k, v in result.iteritems():
        print('%s:%s' % (k, v))


if __name__ == '__main__':
    sendTemplateSMS('15011330375', [], 228368)
    sendTemplateSMS('15011330375', [], 228369)
