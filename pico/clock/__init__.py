import time


def last_sunday(year, month):
    for day in range(31, 24, -1):
        if time.localtime(time.mktime((year, month, day, 0, 0, 0, 0, 0)))[6] == 6:
            return day

    return 31


def sweden_utc_offset_seconds(utc_time):
    month = utc_time[1]
    day = utc_time[2]
    hour = utc_time[3]

    if month < 3 or month > 10:
        return 3600
    if month > 3 and month < 10:
        return 7200

    if month == 3:
        start_day = last_sunday(utc_time[0], 3)
        if day > start_day or (day == start_day and hour >= 1):
            return 7200
        return 3600

    end_day = last_sunday(utc_time[0], 10)
    if day < end_day or (day == end_day and hour < 1):
        return 7200
    return 3600


def localtime():
    utc_time = time.localtime()
    return time.localtime(time.time() + sweden_utc_offset_seconds(utc_time))


def format_time(value=None):
    if value is None:
        value = localtime()

    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*value[:6])
