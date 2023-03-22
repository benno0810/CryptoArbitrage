# !/usr/local/bin/python
# -*- coding:utf-8 -*-
import httplib
import urllib

host = "106.ihuyi.com"
sms_send_uri = "/webservice/sms.php?method=Submit"

# 用户名请登录用户中心->验证码、通知短信->帐户及签名设置->APIID
account = "C16878868"
# 密码 查看密码请登录用户中心->验证码、通知短信->帐户及签名设置->APIKEY
password = "176e1b71eeaa323877e7f"


def send_sms(text, mobile):
    # print "12312317908w ghe9waqhjf-9owaihjrfpioweajrpiofeajwsrpiajeaw",text
    params = urllib.urlencode(
        {'account': account, 'password': password, 'content': text, 'mobile': mobile, 'format': 'json'})
    headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
    conn = httplib.HTTPConnection(host, port=80, timeout=30)
    conn.request("POST", sms_send_uri, params, headers)
    response = conn.getresponse()
    response_str = response.read()
    conn.close()
    return response_str


# if __name__ == '__main__':
#     mobile = ""
#     text = "您的验证码是：121254。请不要把验证码泄露给其他人。"
#
#     print(send_sms(text, mobile))
