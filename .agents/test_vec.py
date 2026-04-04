import sqlite3
try:
    import sqlite_vec
    print("Has sqlite_vec!")
except ImportError:
    print("No sqlite_vec!")
try:
    import pgvector
    print("Has pgvector!")
except ImportError:
    print("No pgvector!")
