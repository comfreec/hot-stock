import sqlite3

conn = sqlite3.connect("fly_db_tmp.db")
conn.row_factory = sqlite3.Row
conn.execute("""CREATE TABLE IF NOT EXISTS trader_users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL UNIQUE,
    app_key_enc TEXT NOT NULL,
    app_secret_enc TEXT NOT NULL,
    account TEXT NOT NULL,
    mock INTEGER DEFAULT 1,
    budget_per INTEGER DEFAULT 300000,
    max_stocks INTEGER DEFAULT 3,
    max_days INTEGER DEFAULT 5,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT
)""")

local = sqlite3.connect("scan_cache.db")
local.row_factory = sqlite3.Row
users = [dict(r) for r in local.execute("SELECT * FROM trader_users").fetchall()]
local.close()

for u in users:
    conn.execute("""INSERT OR REPLACE INTO trader_users
        (user_id,chat_id,app_key_enc,app_secret_enc,account,mock,
         budget_per,max_stocks,max_days,is_active,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (u["user_id"], u["chat_id"], u["app_key_enc"], u["app_secret_enc"],
         u["account"], u["mock"], u["budget_per"], u["max_stocks"],
         u["max_days"], u["is_active"], u["created_at"],
         u.get("updated_at") or u["created_at"]))
    print(f"병합: {u['chat_id']} ({u['account']})")

conn.commit()
rows = conn.execute("SELECT user_id,chat_id,account FROM trader_users").fetchall()
print(f"fly DB 유저 수: {len(rows)}")
for r in rows:
    print(f"  {dict(r)}")
conn.close()
