"""
로컬 trader_users -> fly.io DB 동기화
방식: fly DB 다운로드 -> 유저 데이터 병합 -> 다시 업로드
사용법: python _sync_users_to_fly.py
"""
import sqlite3
import subprocess
import os
import shutil

LOCAL_DB      = "scan_cache.db"
FLY_DB_REMOTE = "/data/scan_cache.db"
FLY_DB_TMP    = "fly_db_tmp.db"

def get_local_users():
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM trader_users").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def run(cmd, stdin_text=None):
    print(f"  $ {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    return subprocess.run(
        cmd, input=stdin_text,
        capture_output=True, text=True, errors="replace", shell=isinstance(cmd, str)
    )

def sync():
    users = get_local_users()
    if not users:
        print("로컬에 유저 없음")
        return
    print(f"로컬 유저 {len(users)}명 발견\n")

    # 1. fly DB 다운로드
    print("1. fly.io DB 다운로드...")
    if os.path.exists(FLY_DB_TMP):
        os.remove(FLY_DB_TMP)
    r = run(["fly", "sftp", "get", FLY_DB_REMOTE, FLY_DB_TMP])
    if not os.path.exists(FLY_DB_TMP):
        print(f"  다운로드 실패 ({r.stderr.strip()[:80]})")
        print("  -> 로컬 DB 복사본 사용")
        shutil.copy(LOCAL_DB, FLY_DB_TMP)
    else:
        print("  완료")

    # 2. 유저 데이터 병합
    print("\n2. 유저 데이터 병합...")
    conn = sqlite3.connect(FLY_DB_TMP)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trader_users (
            user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id        TEXT NOT NULL UNIQUE,
            app_key_enc    TEXT NOT NULL,
            app_secret_enc TEXT NOT NULL,
            account        TEXT NOT NULL,
            mock           INTEGER DEFAULT 1,
            budget_per     INTEGER DEFAULT 300000,
            max_stocks     INTEGER DEFAULT 3,
            max_days       INTEGER DEFAULT 5,
            is_active      INTEGER DEFAULT 1,
            created_at     TEXT NOT NULL,
            updated_at     TEXT
        )
    """)
    for u in users:
        conn.execute("""
            INSERT OR REPLACE INTO trader_users
            (user_id, chat_id, app_key_enc, app_secret_enc, account, mock,
             budget_per, max_stocks, max_days, is_active, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            u["user_id"], u["chat_id"], u["app_key_enc"], u["app_secret_enc"],
            u["account"], u["mock"], u["budget_per"], u["max_stocks"],
            u["max_days"], u["is_active"], u["created_at"],
            u.get("updated_at") or u["created_at"]
        ))
        print(f"  + {u['chat_id']} ({u['account']})")
    conn.commit()
    conn.close()

    # 3. fly DB 업로드
    print("\n3. fly.io DB 업로드...")
    r = run(["fly", "sftp", "shell"], stdin_text=f"put {FLY_DB_TMP} {FLY_DB_REMOTE}\nexit\n")
    if r.returncode == 0:
        print("  완료")
    else:
        print(f"  실패: {r.stderr.strip()[:120]}")

    # 4. 확인
    print("\n4. fly.io 결과 확인...")
    r = run(["fly", "ssh", "console", "-C",
             "sqlite3 /data/scan_cache.db 'SELECT user_id,chat_id,account,is_active FROM trader_users'"])
    print(r.stdout or r.stderr)

    if os.path.exists(FLY_DB_TMP):
        os.remove(FLY_DB_TMP)
    print("동기화 완료!")

if __name__ == "__main__":
    sync()
