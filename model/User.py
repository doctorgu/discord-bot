from dataclasses import dataclass
from .Message import Message
from common import get_point, get_now
from database import open_connection, commit_close_connection


@dataclass
class User:
    display_name: str
    id: str
    _start: Message
    _end: Message
    channel_id_history: int
    point: int

    def __init__(self, author, start, channel_id_history):
        conn, cur = open_connection()

        sql_user = """
insert into user_info
(
    user_id, display_name, target_point
)
values
(
    :user_id, :display_name, 0
)
on conflict(user_id)
do update set
    display_name = :display_name,
    update_time =   case when display_name != :display_name
                    then datetime('now')
                    else update_time
                    end
returning user_id, display_name, target_point, insert_time, update_time
"""
        params_user = {
            "user_id": author.id,
            "display_name": author.display_name
        }
        cur = conn.execute(sql_user, params_user)
        rows = cur.fetchall()
        for (user_id, display_name, target_point, insert_time, update_time) in rows:
            iud = 'I' if insert_time == update_time else 'U'
            sql_user_history = """
insert into user_history
        (iud, user_id, display_name, target_point)
values  (:iud, :user_id, :display_name, :target_point)
"""
            params = {
                "iud": iud,
                "user_id": user_id,
                "display_name": display_name,
                "target_point": target_point,
            }
            cur.execute(sql_user_history, params)

        sql_history = """
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
        params_history = {
            "channel_id": channel_id_history,
            "user_id": author.id,
            "start_time": start.time.strftime("%Y-%m-%d %H:%M:%S"),
            "start_message": start.message,
            "end_time": start.time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_message": ""
        }
        cur.execute(sql_history, params_history)
        
        commit_close_connection(conn)

        self.display_name = author.display_name
        self.id = author.id
        self._start = start
        self._end = Message('')
        self.channel_id_history = channel_id_history

    @property
    def start(self):
        return self._start
    @start.setter
    def start(self, value):
        conn, cur = open_connection()

        sql = """
update  history
set     start_message = :start_message,
        update_time = datetime('now')
where   channel_id = :channel_id
        and user_id = :user_id
        and start_time = :start_time
"""
        params = {
            "start_message": value.message,
            "start_time": self._start.time.strftime("%Y-%m-%d %H:%M:%S"),
            "channel_id": self.channel_id_history,
            "user_id": self.id
        }

        cur.execute(sql, params)
        commit_close_connection(conn)

        self._start.message = value.message;
    
    @property
    def end(self):
        return self._end
    @end.setter
    def end(self, value):
        conn, cur = open_connection()

        sql = """
update  history
set     end_time = :end_time,
        end_message = :end_message,
        update_time = datetime('now')
where   channel_id = :channel_id
        and user_id = :user_id
        and start_time = :start_time
"""
        params = {
            "start_time": self._start.time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": value.time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_message": value.message,
            "channel_id": self.channel_id_history,
            "user_id": self.id
        }

        cur.execute(sql, params)
        commit_close_connection(conn)

        self._end = value;
    
    def to_string(self):
        # %Y-%m-%d
        start_time = self._start.time.strftime('%H:%M:%S')
        start_msg = self._start.message

        point = get_point(self._start, self._end)
        end_time = self._end.time.strftime('%H:%M:%S')
        end_msg = self._end.message

        ret = f'{self.display_name}: {start_time} ~ {end_time}: {round(point, 2)} {end_msg if end_msg else start_msg}'
        return ret
