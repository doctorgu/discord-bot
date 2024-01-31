from discord.ext import tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone
import re
import discord
import sys
import sqlite3
from common import get_now, get_monday_this_week
from database import open_connection, commit_close_connection
from model.Message import Message
from model.User import User
from config import schedule_bot, test_bot, CHANNEL_ID, PREFIX, START_HOUR, TARGET_POINT_PER_WEEK

# %Y-%m-%d %H:%M:%S


TOKEN_SCHEDULE_BOT = schedule_bot['TOKEN']
TOKEN_TEST_BOT = test_bot['TOKEN']
channel_id_main = ''
channel_id_history = ''

# start: { time, message }, end: { time, message }
users = {}
# to edit today message
msg_per_ch = {}
# to initialize if day changed
now_prev = get_now()


def get_cmd_msg(content):
    m = re.search(rf'{PREFIX}(\w+)(?: (.+))?', content)
    if not m:
        return ('', '')

    cmd = m.group(1)
    msg = m.group(2)
    if not msg:
        msg = ''
    return (cmd, msg)


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def do_if_day_or_week_change():
    global now_prev

    now = get_now()
    if now_prev.day != now.day:
        print(f'day changed from {now_prev} to {now}')
        # initialize to prevent to have yesterday information
        users.clear()
        msg_per_ch.clear()

    now_prev = now


async def edit_message(channel, msg):
    if channel in msg_per_ch:
        await msg_per_ch[channel].edit(content=msg)
    else:
        msg_per_ch[channel] = await channel.send(msg)

def upsert_history(channel_id, users):
    conn, cur = open_connection()

    for user_id, user in users.items():
        sql_upsert = """
insert into history
(
    channel_id, user_id,
    start_time, start_message,
    end_time, end_message
)
values
(
    :channel_id, :user_id,
    :start_time, :start_message,
    :end_time, :end_message
)
on conflict(channel_id, user_id, start_time)
do update set
    start_message = :start_message,
    end_time =      :end_time,
    end_message =   :end_message,
    update_time =   datetime('now')
"""
        start_time = user.start.time.strftime("%Y-%m-%d %H:%M:%S")
        start_message = user.start.message
        end_time = user.end.time.strftime("%Y-%m-%d %H:%M:%S")
        end_message = user.end.message
        params_upsert = {
            "channel_id": channel_id,
            "user_id": user_id,
            "start_time": start_time,
            "start_message": start_message,
            "end_time": end_time,
            "end_message": end_message,
        }
        cur.execute(sql_upsert, params_upsert)


    sql_point = """
with pnt as
(
	select	user_id, start_time, start_message, end_time, end_message,
            (julianday(end_time) - julianday(start_time))
            * 24 * 60
            / (60 - c.error_range_minute)
            * c.point_per_hour point
	from	history h
			cross join config c
	where	channel_id = :channel_id
            and start_time >= :monday_this_week
)
, p_tm as
(
	select	rank() over (partition by user_id order by strftime('%Y-%m-%d', start_time) desc) rnum,
			user_id,
			strftime('%Y-%m-%d', start_time) start_date,
			start_time, start_message, end_time, end_message,
			point
	from	pnt
			cross join config c
)
, p_dt as
(
	select	user_id, strftime('%Y-%m-%d', start_time) start_date,
			case
			when sum(point) < c.default_point then c.default_point
			when sum(point) > c.max_point_per_day then c.max_point_per_day 
			else sum(point) end point
	from	p_tm
			cross join config c
	group by user_id, strftime('%Y-%m-%d', start_time)
)
, p_wk as
(
	select	user_id, sum(point) point
	from	p_dt
	group by user_id
)
select	p_tm.user_id, u.display_name,
		p_tm.point, p_dt.point point_day, p_wk.point point_week,
        c.target_point_per_week + u.target_point target_point,
		strftime('%Y-%m-%d', p_tm.start_date) start_date, strftime('%H:%M:%S', p_tm.start_time) start_time, p_tm.start_message,
        strftime('%H:%M:%S', p_tm.end_time) end_time, p_tm.end_message		
from	p_tm
		inner join user_info u
		on u.user_id = p_tm.user_id
		inner join p_dt
		on p_dt.user_id = p_tm.user_id
		and p_dt.start_date = p_tm.start_date
		inner join p_wk
		on p_wk.user_id = p_tm.user_id
        cross join config c
where	p_tm.rnum = 1
order by u.display_name, start_time
"""
    monday_this_week = get_monday_this_week().strftime("%Y-%m-%d")
    today = get_now().strftime("%Y-%m-%d")
    params_point = {
        "channel_id": channel_id,
        "monday_this_week": monday_this_week,
        "today": today
    }
    cur = conn.execute(sql_point, params_point)
    rows = cur.fetchall()

    commit_close_connection(conn)

    return rows


def update_user_target_point(user_id, point_week):
    conn, cur = open_connection()

    sql = """
update	user_info
set 	target_point = max(0, target_point + (u.target_point_per_week - :point_week)),
		update_time = datetime('now')
from 	(
			select	u.user_id, c.target_point_per_week
			from	user_info u
					cross join config c
			where	user_id = :user_id
		) u
where	user_info.user_id = u.user_id
returning user_id, display_name, target_point;
"""
    params = {
        "point_week": point_week,
        "user_id": user_id
    }
    cur = conn.execute(sql, params)
    rows = cur.fetchall()

    for (user_id, display_name, target_point) in rows:
        sql = """
insert into user_history
        (iud, user_id, display_name, target_point)
values  ('U', :user_id, :display_name, :target_point)
"""
        params = {
            "user_id": user_id,
            "display_name": display_name,
            "target_point": target_point,
        }
        cur.execute(sql, params)


    commit_close_connection(conn)


async def write_history(is_23_59):
    global now_prev

    channel_his = client.get_channel(channel_id_history)

    rows_point = upsert_history(channel_id_history, users)

    user_ids = []

    now = get_now()
    weekday = now.isocalendar().weekday
    now_ymd = now.strftime("%Y-%m-%d")

    msg_all = f'## {now_ymd}\n'
    for (user_id, display_name,  point, point_day, point_week, target_point, start_date, start_time, start_message, end_time, end_message) in rows_point:
        msg = ''
        if user_id not in user_ids:
            msg += f"### {display_name}: {round(point_day, 2)}, {round(point_week, 2)} / {round(target_point, 2)}\n"
            user_ids.append(user_id)

            if is_23_59 and weekday == 7 and point_week != TARGET_POINT_PER_WEEK:
                update_user_target_point(user_id, point_week)

        msg += f"""{f"{start_date} " if start_date != now_ymd else ""}{start_time} ~ {end_time} ({round(point, 2)})
> Plan: {start_message}
> Result: {end_message}
"""
        msg_all += msg    

    await edit_message(channel_his, msg_all)
    


@client.event
async def on_ready():
    do_if_day_or_week_change()

    interval.start()
    # ch = client.get_channel(CH_HISTORY)
    # async for msg in ch.history(limit=100):
    #     print(msg.content)


@tasks.loop(minutes=1)
async def interval():
    do_if_day_or_week_change()

    now = get_now()
    if now.hour == START_HOUR and now.minute == 0:
        channel = client.get_channel(channel_id_main)
        await channel.send(
            """시작할 때: !시작 메세지
종료할 때: !종료 메세지
""")
    elif now.hour == 23 and now.minute == 59:
        await write_history(True)


@client.event
async def on_message(message):
    if message.channel.id != channel_id_main:
        return

    user_id = message.author.id
    if user_id == client.user.id:
        return

    channel = client.get_channel(channel_id_main)

    cmd, msg = get_cmd_msg(message.content)
    if not cmd:
        return

    if cmd in ('start', '시작'):
        user = None
        if user_id in users:
            user = users[user_id]
            user.start = Message(msg)
        else:
            user = User(message.author, Message(msg), channel_id_history)
            users[user_id] = user

        await channel.send(user.to_string())
    elif cmd in ('end', '종료'):
        user = None
        if not user_id in users:
            await channel.send(f'use {PREFIX}start first.')
            return

        user = users[user_id]
        user.end = Message(msg)
        msg_user = user.to_string()
        users.pop(user_id)

        await channel.send(msg_user)
    elif cmd in ('status', '상태'):
        if not users:
            await channel.send(f'No user')
            return

        ret = ''
        for user in users.values():
            ret += user.to_string() + '\n'

        await channel.send(ret)
    elif cmd in ('log', '기록'):
        await write_history(False)

    else:
        await channel.send(f'Wrong cmd:{cmd}')

bot = sys.argv[1] if len(sys.argv) >= 2 else ''
if bot == 'schedule-bot':
    channel_id_main = CHANNEL_ID['9_TO_11']
    channel_id_history = CHANNEL_ID['9_TO_11_HISTORY']
    client.run(TOKEN_SCHEDULE_BOT)
elif bot == '' or bot == 'test-bot':
    channel_id_main = CHANNEL_ID['SQLD_TEXT']
    channel_id_history = CHANNEL_ID['SQLD_HISTORY']
    client.run(TOKEN_TEST_BOT)
else:
    print(f'Wrong bot:{bot}')
