import sqlite3
import json

def test():
    try:
        import sqlite_vec
    except ImportError:
        with open("/mnt/e/OS Twin/os-twin/.agents/vec_test.log", "w") as f:
            f.write("no sqlite_vec")
        return

    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_items USING vec0(
                id TEXT PRIMARY KEY,
                embedding float[4]
            )
        """)
        with open("/mnt/e/OS Twin/os-twin/.agents/vec_test.log", "w") as f:
            f.write("success creating TEXT PRIMARY KEY\n")
    except Exception as e:
        with open("/mnt/e/OS Twin/os-twin/.agents/vec_test.log", "w") as f:
            f.write(f"failed creating TEXT PRIMARY KEY: {e}\n")

if __name__ == "__main__":
    test()
