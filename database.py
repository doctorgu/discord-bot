import sqlite3

def open_connection():
    conn = sqlite3.connect('discord.db')
    cur = conn.cursor()
    return (conn, cur)

def commit_close_connection(conn):
    conn.commit()
    conn.close()

# def create_tables():
#     conn, cur = open_connection()
    
#     sql = """
# create table if not exists history (
#     channel_id int not null,
#     user_id int not null,
#     yyyymmdd text not null,
#     start_time datetime not null,
#     end_time datetime not null,
#     start_message text not null,
#     end_message text not null,
#     point int not null,
#     insert_time datetime default current_timestamp,
#     update_time datetime default current_timestamp,
#     constraint pk_history primary key (channel_id, user_id, yyyymmdd)
# )
# """
#     cur.execute(sql)

#     sql = """
# create table if not exists user_info (
#     user_id int not null,
#     display_name text not null,
#     target_point float not null default 0,
#     insert_time datetime not null default current_timestamp,
#     update_time datetime not null default current_timestamp,
#     constraint pk_history primary key (user_id)
# )
# """
#     cur.execute(sql)

#     sql = """
# create table if not exists create table user_history (
# 	  seq integer primary key autoincrement,
# 	  iud varchar(1) not null,
# 	  user_id int not null,
# 	  display_name text not null,
# 	  target_point float not null,
# 	  insert_time datetime not null default current_timestamp
# );
# """
#     cur.execute(sql)

#     commit_close_connection(conn)