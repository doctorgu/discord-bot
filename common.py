from datetime import datetime, date, timedelta, timezone
from config import HOURS_OFFSET, DEFAULT_POINT, ERROR_RANGE_MINUTE, POINT_PER_HOUR, MAX_POINT_PER_DAY


def get_now():
    return datetime.now(timezone(timedelta(hours=HOURS_OFFSET)))

def get_point(start, end):
    # 19:22:22 ~ 20:57:47
    # .5 for 59 minutes
    point = (end.time - start.time).total_seconds() / 60 / (60 - ERROR_RANGE_MINUTE) * POINT_PER_HOUR
    if point < DEFAULT_POINT:
        point = DEFAULT_POINT

    return min(point, MAX_POINT_PER_DAY)

def get_monday_this_week():
    now = get_now()
    today_weekday = now.isocalendar().weekday
    monday = now - timedelta(days=today_weekday - 1)
    return monday
