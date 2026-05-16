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

def initialize_database(logger=None):
    db = create_connection(DATABASE)
    if db is None:
        raise RuntimeError("Could not open SQLite database during initialization")

    try:
        cursor = db.cursor()
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_discord_id ON Users(discord_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_total_xp ON Users(total_xp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_total_xp_desc ON Users(total_xp DESC);")
        db.commit()
    except sqlite3.Error:
        if logger is not None:
            logger.exception("Failed to initialize SQLite indexes")
        raise
    finally:
        db.close()
