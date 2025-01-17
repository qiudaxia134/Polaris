# -*-* coding:UTF-8
import re
import prettytable
from itertools import chain


def merge_same_data(data, result):
    if isinstance(data, list):
        result = {}
        for one in data:
            merge_same_data(one, result)
        return result
    elif isinstance(data, dict):
        for key, value in data.items():
            if not value:
                continue
            if isinstance(value, list):
                if key not in result.keys():
                    result[key] = []
                """ 数据去重 """
                if isinstance(value[0], dict):
                    value = [dict(t) for t in set([tuple(d.items()) for d in value])]
                if isinstance(value[0], list):
                    value = [_ for _ in chain(*value) if _ != '']
                if isinstance(value[0], str):
                    value = list(set(value))
                for i in value:
                    if i not in result[key]:
                        result[key].append(i)
            elif isinstance(value, dict):
                if key not in result.keys():
                    result[key] = {}
                if value not in result[key]:
                    result[key].update(value)
            else:
                if key not in result.keys():
                    result[key] = value
                elif value != result[key]:
                    result[key] = [value, result[key]]
        return result
    else:
        return data


def keep_data_format(data):
    """ 统一数据格式 字典键一致 """

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list) and len(value) != 0:
                result = []
                fill_data = {_: '' for i in value if isinstance(i, dict) for _ in i.keys()}
                if fill_data:
                    for one in value:
                        copy_data = fill_data.copy()
                        if isinstance(one, dict):
                            copy_data.update(one)
                        elif isinstance(one, list):
                            for i in one:
                                copy_data.update(i)
                        result.append(copy_data)
                    """ 数据去重 """
                    # result = [dict(t) for t in set([tuple(d.items()) for d in result])]
                    data[key] = result
                else:
                    data[key] = value
            else:
                data[key] = value
    return data


def get_table_form(data, seq=500, layout='horizontal', border=True, align='c', title=None, rank=True):
    """ 获得表单数据 """

    tb = prettytable.PrettyTable(border=border)
    if layout == 'horizontal':
        if isinstance(data[0], dict):
            if rank:
                title_list = ['id'] + list(data[0].keys())
            else:
                title_list = list(data[0].keys())
        else:
            title_list = title or ['id', 'info']
        tb.field_names = title_list
        for title in title_list:
            tb.align[title] = align
        for index, one in enumerate(data[:seq]):
            if isinstance(one, dict):
                col_len = int(120 / (len(one.values()) + 1))
                one_value = [
                    str(_).strip()[:col_len] + ' ...' if len(str(_)) > col_len else str(_).strip() for _ in one.values()
                ]
            else:
                one_value = [str(one).strip()]
            if rank:
                tb.add_row([str(index + 1) if index < seq else '...'] + one_value)
            else:
                tb.add_row(one_value)
    elif layout == 'vertical':
        tb.field_names = title or ['key', 'value']
        if isinstance(data, list) and len(data) == 1:
            data = data[0]
        for key, value in data.items():
            if isinstance(value, list):
                value = ','.join([str(i) for i in value])
            value = (value, str(value)[:120] + '...')[len(str(value)) > 120]
            tb.add_row([key, value])
            tb.align[key] = align
    else:
        raise Exception('Parameter error')

    return tb


def parse_raw_request(raw):

    options, flag = {'headers': {}}, False
    for line in raw.split('\r\n'):
        match = re.search(r"\A([A-Z]+) (.+) HTTP/[\d.]+\Z", line)
        if match:
            options['method'], options['path'] = match.groups()
        elif re.search(r"\A\S+:", line):
            name, value = line.split(':', 1)
            options['headers'][name] = value
    if options['method'] == 'POST':
        options['data'] = raw.split('\r\n\r\n', 1)[1]

    return options


def ip_to_long(str_ip):
    try:
        ip_list = [int(single_ip) for single_ip in str_ip.split('.')]
        return bin((ip_list[0] << 24) + (ip_list[1] << 16) + (ip_list[2] << 8) + ip_list[3])
    except Exception as e:
        return bin(0)


def long_to_ip(int_ip):
    ip_list = [
        str(eval(int_ip) >> 24),
        str((eval(int_ip) & 0xffffff) >> 16),
        str((eval(int_ip) & 0xffff) >> 8),
        str((eval(int_ip) & 0xff))
    ]
    return '.'.join(ip_list)


class Interval(object):
    def __init__(self):
        self.st = bin(0)
        self.ed = bin(0)

    def change(self, new_st, new_ed):
        self.st = new_st
        self.ed = new_ed


def merge_ip_segment(ip_list):
    """ 网段合并处理 """
    try:
        ip_interval = []
        ip_tmp = [ip_to_long('0.0.0.0'), ip_to_long('0.0.0.0')]
        for ip_range in ip_list:
            if '-' in ip_range:
                interval_tmp = Interval()
                tmp = ip_range.split('-')
                if len(tmp) == 2:
                    ip_tmp[0] = (ip_to_long(tmp[0]))
                    ip_tmp[1] = (ip_to_long(tmp[1]))
                    interval_tmp.change(ip_tmp[0], ip_tmp[1])
                    ip_interval.append(interval_tmp)
            elif '/' in ip_range:
                interval_tmp = Interval()
                tmp = ip_range.split('/')
                if len(tmp) == 2:
                    ip1 = tmp[0]
                    ip2 = tmp[1]
                    ip1_tmp = ip1.split('.')
                    if ip1[-1] == '0':
                        ip1 = ip1[:-1] + '1'
                    for i in range(len(ip1_tmp)):
                        ip1_tmp[i] = bin(int(ip1_tmp[i]))[2:].rjust(8)
                        ip1_tmp[i] = ip1_tmp[i].replace(' ', '0')
                    ip1_tmp = ''.join(ip1_tmp)
                    ip2_tmp = ip1_tmp[0:int(ip2)].ljust(32)
                    ip2_tmp = ip2_tmp.replace(' ', '1')
                    ip1_tmp = []
                    for j in range(0, 31, 8):
                        ip1_tmp.append(str(int(ip2_tmp[j:j + 8], base=2)))
                    ip2 = '.'.join(ip1_tmp)
                    interval_tmp.change(ip_to_long(ip1), ip_to_long(ip2))
                    ip_interval.append(interval_tmp)
            else:
                interval_tmp = Interval()
                interval_tmp.change(ip_to_long(ip_range), ip_to_long(ip_range))
                ip_interval.append(interval_tmp)

        interval_tmp = Interval()
        intervals = [interval_tmp]
        if len(ip_interval) == 0: return intervals
        ip_interval.sort(key=lambda intervals_sort: int(intervals_sort.st, base=2))
        intervals[0] = ip_interval[0]
        for i in range(1, len(ip_interval)):
            if int(ip_interval[i].st, base=2) <= int(intervals[len(intervals) - 1].ed, base=2):
                max_ed = max(int(ip_interval[i].ed, base=2), int(intervals[len(intervals) - 1].ed, base=2))
                intervals[len(intervals) - 1].ed = bin(max_ed)
            else:
                intervals.append(ip_interval[i])

        ip_list = []
        for interval in intervals:
            if interval.st != interval.ed:
                ip_list.append(long_to_ip(interval.st) + '-' + long_to_ip(interval.ed))
            else:
                ip_list.append(long_to_ip(interval.st))
        return ip_list
    except:
        pass
