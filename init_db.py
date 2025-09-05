import sqlite3
from pathlib import Path

DB_PATH = Path("labelforge.db")
SCHEMA_PATH = Path("schema.sql")

def run_schema():
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    con = sqlite3.connect(DB_PATH)
    try:
        con.executescript(sql)
        con.commit()
    finally:
        con.close()

def seed_demo_data():
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        # Demo admin χρήστης (στο επόμενο βήμα θα βάλουμε hashing)
        cur.execute(
            "INSERT OR IGNORE INTO users(email, password_hash, role) VALUES(?,?,?)",
            ("admin@example.com", "dev", "admin"),
        )
        # Demo project (id=1 για ευκολία)
        cur.execute(
            "INSERT OR IGNORE INTO projects(id, name, type) VALUES(?,?,?)",
            (1, "Demo – Text Classification", "text"),
        )
        con.commit()
    finally:
        con.close()

if __name__ == "__main__":
    run_schema()
    seed_demo_data()
    print("Database initialized ✔")
