import sqlite3
try:
    import sqlite_vec
    print("sqlite_vec imported")
except ImportError:
    print("no sqlite_vec")
