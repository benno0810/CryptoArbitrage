# -*- coding: utf-8 -*-

import sys

import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr


my_sender = 'tjxcs@qq.com'  # 发件人邮箱账号
pwd = 'pwpntxqwqccabbcj'    # 发件人邮箱密码(当时申请smtp给的口令)
#to = ['tjxcs@qq.com']         # 收件人邮箱账号
to = ['tjxiter@163.com', '526970401@qq.com']         # 收件人邮箱账号  tjx, hq
mail_host = 'smtp.qq.com'

def send(title, msg, send_name, to=to):

    ret = True
    try:
        msg = MIMEText(msg, 'plain', 'utf-8')
        msg['From'] = formataddr([send_name, my_sender])    # 括号里的对应发件人邮箱昵称、发件人邮箱账号
        #msg['To'] = formataddr([to_name, to])               # 括号里的对应收件人邮箱昵称、收件人邮箱账号
        msg['Subject'] = title                              # 邮件的主题，也可以说是标题

        server = smtplib.SMTP_SSL("smtp.qq.com", 465)       # 发件人邮箱中的SMTP服务器，端口是465
        server.login(my_sender, pwd)                        # 括号中对应的是发件人邮箱账号、邮箱密码
        server.sendmail(my_sender, to, msg.as_string()) # 括号中对应的是发件人邮箱账号、收件人邮箱账号、发送邮件
        server.quit()                                       # 关闭连接
    except Exception:                                       # 如果 try 中的语句没有执行，则会执行下面的 ret=False
        ret = False
    return ret


def test():
    res = send('market: {}, function: {}, timeout'.format('okex', sys._getframe().f_code.co_name),
               'market: {}, function: {}, timeout'.format('okex', sys._getframe().f_code.co_name), 'tjx')
    if res:
        print('send successfully')
    else:
        print('send failed')

if __name__  == '__main__':
    test()