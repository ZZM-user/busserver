import datetime
import os
import smtplib
import threading
import time
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
import json
import jsonpath
import pprint


def get_html(startStation, endStation, timeStamp):
    # 模拟请求
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,zh-HK;q=0.6',
        'Connection': 'keep-alive',
        'Content-Length': '124',
        'Content-Type': 'application/json; charset=UTF-8',
        'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="90", "Google Chrome";v="90"',
        'sec-ch-ua-mobile': '?0',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
        'Host': 'busserver.cqyukexing.com',
        'Origin': 'https://www.96096kp.com',
        'Referer': 'https://www.96096kp.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.72 Safari/537.36',
    }
    data = {
        'departureName': startStation,
        'destinationId': 'null',
        'destinationName': endStation,
        'opSource': '7',
        # 指定日期时间戳
        'queryDate': timeStamp,
    }
    data = json.dumps(data)
    url = 'https://busserver.cqyukexing.com/busticket/schedule_list_310?channel=7'
    response = requests.post(url, headers=headers, data=data, timeout=5)
    if response.status_code == 200:
        html = response.text
        # print(html)
        return html


def parse_html(html):
    # 解析获取的数据
    items = []
    html = json.loads(html)
    for i in range(len(jsonpath.jsonpath(html, '$..scheduleInfo'))):
        item = {}
        timeStamp = jsonpath.jsonpath(html, '$..scheduleInfo..departureTime')[i]
        item["发车日期"] = time.strftime("%Y-%m-%d", time.localtime(timeStamp))
        # 检测是否过期
        out_data(item["发车日期"])
        item["发车时间"] = jsonpath.jsonpath(html, '$..scheduleInfo..departureTimeDesc')[i]
        item["起始站"] = jsonpath.jsonpath(html, '$..departureStation..name')[i]
        # item["地址"] = jsonpath.jsonpath(html, '$..departureStation..addr')[i]
        item["终点站"] = jsonpath.jsonpath(html, '$..destinationStation..name')[i]
        item["余票"] = jsonpath.jsonpath(html, '$..scheduleInfo..remainSeatCnt')[i]
        item["票价"] = jsonpath.jsonpath(html, '$..scheduleInfo..fullTicketPrice')[i]
        item["车型"] = jsonpath.jsonpath(html, '$..scheduleInfo..busType')[i]
        item["车牌号"] = jsonpath.jsonpath(html, '$..scheduleInfo..scheduleCode')[i]
        item["路线"] = jsonpath.jsonpath(html, '$..scheduleInfo..lineName')[i][3:]
        item["状态"] = '\033[32m' if item["余票"] > 0 else '\033[31m'
        # item["途径"] = jsonpath.jsonpath(html, '$..scheduleInfo..stopStation')[i]
        items.append(item)
    return items


def watch_ticks(bus_list):
    # 检查目前还有票的车次
    format_info(bus_list)
    has_ticks = []
    filename = 'tick_log of ' + bus_list[0]["起始站"] + '-' + bus_list[0]["终点站"] + '.txt'
    if not os.path.exists('./logs/' + filename):
        f = open('./logs/' + filename, 'w')
        f.close()
    with open('./logs/' + filename, 'r+', encoding='utf-8') as file:
        alreald_send = file.read()
    for bus in bus_list:
        if bus["余票"] != 0 and bus["发车时间"] not in alreald_send or not len(alreald_send):
            has_ticks.append(bus)
            with open('./logs/tick_log of ' + bus["起始站"] + '-' + bus["终点站"] + '.txt', 'a+', encoding='utf-8') as file:
                file.write(bus["发车时间"] + '\n')
    # print(has_ticks)
    return has_ticks


def out_data(date):
    # 检查车票跟踪是否过时
    # 是否过期一天
    tomorrow = datetime.date.today() - datetime.timedelta(days=1)
    if date == tomorrow:
        print("车票跟踪已过时！")
        os.exit(0)


def format_info(bus_list):
    print(bus_list[0]["发车日期"] + '\t' + bus_list[0]["起始站"] + '-' + bus_list[0]["终点站"])
    print('-' * 120)
    # print("\t发车时间"
    #       "\t\t\t起始站"
    #       "\t\t\t终点站"
    #       "\t\t余票"
    #       "\t\t票价"
    #       "\t\t路线"
    #       "\t\t车型"
    #       "\t\t车牌号")
    for bus in bus_list:
        print(bus["状态"] + "\t" + bus["发车时间"],
              "\t\t" + bus["起始站"],
              "\t\t" + bus["终点站"],
              "\t\t" + str(bus["余票"]),
              "\t\t\t" + str(bus["票价"]),
              "\t\t" + bus["路线"],
              "\t\t" + bus["车型"],
              "\t\t" + bus["车牌号"] + '\033[0m')
    print('-' * 120)


def send_email(sendUser, mail_user, mail_pass, receivers, start, end, tick_date, message):
    """发送邮件"""
    # 第三方 SMTP 服务
    mail_host = 'smtp.qq.com'  # 设置服务器
    sender = mail_user

    # 创建一个带附件的案例
    mail = MIMEMultipart()

    mail['From'] = Header(sendUser, 'utf-8')
    mail['To'] = ";".join(receivers)
    subject = '愉客行有新的票务情况：' + tick_date + '-' + start + '-' + end  # 邮件标题
    mail['Subject'] = Header(subject, 'utf-8')

    # 邮件正文内容
    mail.attach(MIMEText(message, 'plain', 'utf-8'))

    try:
        smtpObj = smtplib.SMTP()
        smtpObj.connect(mail_host, 25)  # 25为端口号
        smtpObj.login(mail_user, mail_pass)
        smtpObj.sendmail(sender, receivers, mail.as_string())
        print(receivers + "\t发送成功")  # 邮件发送成功
    except Exception as e:
        pass
    finally:
        smtpObj.quit()


def main():
    global timer_times
    timer_times = timer_times + 1
    for i in range(len(startStation)):
        html = get_html(startStation[i], endStation[i], timeStamp[i])
        bus_list = parse_html(html)
        # pprint.pprint(bus_list)
        has_ticks = watch_ticks(bus_list)
        json.dump(bus_list,
                  open('./data/bus_list of ' + startStation[i] + '-' + endStation[i] + '.json', 'a+', encoding='utf-8'),
                  ensure_ascii=False)
        if len(has_ticks):
            json.dump(has_ticks, open('./data/has_ticks of ' + startStation[i] + '-' + endStation[i] + '.json', 'w+',
                                      encoding='utf-8'), ensure_ascii=False)
            message = '\n'.join([str(tick).replace(',', '\n') for tick in has_ticks])
            send_email(sendUser[i], mail_user[i], mail_pass[i], receivers[i], startStation[i], endStation[i],
                       ticksDate[i], message)
    # 定时延迟
    now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    log_message = ("\n定时任务已触发至：第%s轮\n当前时间：%s\n" % (timer_times, now))
    with open("./logs/log.txt", 'a+', encoding="utf-8") as file:
        file.write(log_message)
    print(log_message)
    time.sleep(1800)
    timer = threading.Timer(1800, main())
    timer.start()


if __name__ == '__main__':
    with open('config.json', 'r', encoding='utf-8') as file:
        config = json.load(file)
    startStation = config["起始站"]
    endStation = config["终点站"]
    ticksDate = config["车票日期"]
    timeArray = [time.strptime(tick_date + ' 00:00:00', "%Y-%m-%d %H:%M:%S") for tick_date in config["车票日期"]]
    timeStamp = [int(time.mktime(times)) for times in timeArray]
    sendUser = config["发送人"]
    mail_user = config["用户名"]
    mail_pass = config["第三方客户端授权码"]
    receivers = config["接收方"]
    # 定时延迟
    timer_times = 0
    timer = threading.Timer(1800, main())
    timer.start()
