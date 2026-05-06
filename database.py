import sqlite3

DATABASE = "SQLitePython.db"

"""
CREATE TABLE Users(
id              INTEGER
discord_id      TEXT 
avatar          TEXT 
discriminator   INTEGER
username        TEXT
level           INTEGER
xp_level        INTEGER 
xp_cap          INTEGER
total_xp        INTEGER
message_count   INTEGER)
"""

def create_connection(db_file):
    try:
        conn = sqlite3.connect(db_file, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except sqlite3.Error as e:
        print(e)
    return None