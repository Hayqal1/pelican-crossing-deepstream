#!/usr/bin/env python3
"""
Penyimpanan pelanggaran Pelican Crossing ke SQLite (ringan, tanpa server).
- Penulisan lewat antrean + thread terpisah, jadi pipeline DeepStream tidak tertahan I/O disk.
- File database default: data/pelanggaran.db (ubah lewat env DB_PATH).
- Data lebih tua dari DB_RETENSI_HARI (default 90) dihapus otomatis saat program mulai.

Lihat isi database:   python3 db_pelanggaran.py            (rekap hari ini + 20 data terakhir)
                      python3 db_pelanggaran.py 2026-10-12 (rekap tanggal tertentu)
"""
import os
import sys
import queue
import sqlite3
import datetime
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "data", "pelanggaran.db"))
RETENSI_HARI = int(os.environ.get("DB_RETENSI_HARI", "90"))

_antrean = queue.Queue()
_thread = None

SKEMA = """
CREATE TABLE IF NOT EXISTS pelanggaran (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    waktu     TEXT NOT NULL,          -- 'YYYY-MM-DD HH:MM:SS'
    tipe      TEXT NOT NULL,          -- PEJALAN_KAKI / KENDARAAN / TOMBOL
    kamera    TEXT,                   -- KAM1 / KAM2 / -
    state_plc INTEGER,
    track_id  INTEGER,
    kelas     TEXT,                   -- person / car / motorcycle / bus / truck
    info      TEXT
);
CREATE INDEX IF NOT EXISTS idx_pelanggaran_waktu ON pelanggaran(waktu);
CREATE INDEX IF NOT EXISTS idx_pelanggaran_tipe  ON pelanggaran(tipe);

CREATE TABLE IF NOT EXISTS perubahan_state (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    waktu      TEXT NOT NULL,
    state_lama INTEGER,
    state_baru INTEGER
);
CREATE INDEX IF NOT EXISTS idx_state_waktu ON perubahan_state(waktu);
"""


def _buka(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")      # bisa dibaca sambil ditulis
    con.execute("PRAGMA synchronous=NORMAL")    # hemat tulis ke disk (aman untuk WAL)
    con.executescript(SKEMA)
    return con


def _pekerja():
    con = _buka()
    batas = (datetime.datetime.now() - datetime.timedelta(days=RETENSI_HARI)).strftime("%Y-%m-%d")
    con.execute("DELETE FROM pelanggaran WHERE waktu < ?", (batas,))
    con.execute("DELETE FROM perubahan_state WHERE waktu < ?", (batas,))
    con.commit()
    while True:
        item = _antrean.get()
        if item is None:
            break
        sql, data = item
        try:
            con.execute(sql, data)
            # commit per batch: tulis semua yang sudah mengantre sekaligus
            while not _antrean.empty():
                nxt = _antrean.get_nowait()
                if nxt is None:
                    con.commit()
                    con.close()
                    return
                con.execute(*nxt)
            con.commit()
        except Exception as e:
            print(f"[!] Gagal menyimpan ke database: {e}", flush=True)
    con.commit()
    con.close()


def _waktu():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def mulai():
    """Panggil sekali saat program mulai."""
    global _thread
    if _thread is None:
        _thread = threading.Thread(target=_pekerja, daemon=True)
        _thread.start()


def simpan_pelanggaran(tipe, kamera, state_plc, track_id=None, kelas="", info=""):
    track_id = int(track_id) if str(track_id).strip().lstrip("-").isdigit() else None
    _antrean.put(("INSERT INTO pelanggaran (waktu, tipe, kamera, state_plc, track_id, kelas, info) "
                  "VALUES (?,?,?,?,?,?,?)",
                  (_waktu(), tipe, kamera, state_plc, track_id, kelas, info)))


def simpan_state(state_lama, state_baru):
    _antrean.put(("INSERT INTO perubahan_state (waktu, state_lama, state_baru) VALUES (?,?,?)",
                  (_waktu(), state_lama, state_baru)))


def tutup():
    """Panggil saat program berhenti: tulis sisa antrean lalu tutup database."""
    if _thread is not None:
        _antrean.put(None)
        _thread.join(timeout=5)


def rekap(tanggal=None):
    """Kembalikan {tipe: jumlah} untuk tanggal 'YYYY-MM-DD' (default hari ini)."""
    tanggal = tanggal or datetime.date.today().isoformat()
    con = _buka()
    hasil = dict(con.execute("SELECT tipe, COUNT(*) FROM pelanggaran WHERE waktu LIKE ? GROUP BY tipe",
                             (tanggal + "%",)).fetchall())
    con.close()
    return hasil


if __name__ == "__main__":
    tgl = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    print(f"Database : {DB_PATH}")
    print(f"Rekap {tgl}: {rekap(tgl) or 'belum ada pelanggaran'}")
    con = _buka()
    print("\n20 pelanggaran terakhir:")
    print(f"{'id':>5}  {'waktu':19}  {'tipe':12}  {'kamera':6}  {'state':5}  {'track':6}  kelas")
    for r in con.execute("SELECT id, waktu, tipe, kamera, state_plc, track_id, kelas "
                         "FROM pelanggaran ORDER BY id DESC LIMIT 20"):
        print(f"{r[0]:>5}  {r[1]:19}  {r[2]:12}  {str(r[3]):6}  {str(r[4]):5}  {str(r[5] or '-'):6}  {r[6] or '-'}")
    con.close()