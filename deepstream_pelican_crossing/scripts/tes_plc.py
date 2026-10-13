#!/usr/bin/env python3
"""
Tes koneksi PLC Modbus TCP tanpa menjalankan DeepStream.
    python3 scripts/tes_plc.py                 -> baca register State (default alamat 0) tiap 0.5 s
    python3 scripts/tes_plc.py --scan 0 20     -> tampilkan isi holding register 0..19 (cari alamat)
Pengaturan sama dengan program utama: PLC_IP, PLC_PORT, PLC_UNIT, PLC_REG_STATE, PLC_REG_PBCOUNTER
"""
import os
import sys
import time

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    try:
        from pymodbus.client.sync import ModbusTcpClient
    except ImportError:
        sys.exit("[!] pymodbus belum terpasang: pip3 install pymodbus")

IP = os.environ.get("PLC_IP", "192.168.200.100")
PORT = int(os.environ.get("PLC_PORT", "502"))
UNIT = int(os.environ.get("PLC_UNIT", "1"))
REG_STATE = int(os.environ.get("PLC_REG_STATE", "0"))
REG_PB = int(os.environ.get("PLC_REG_PBCOUNTER", "-1"))


def baca(client, addr, count=1):
    for kw in ({"count": count, "device_id": UNIT}, {"count": count, "slave": UNIT},
               {"count": count, "unit": UNIT}, {"count": count}):
        try:
            return client.read_holding_registers(addr, **kw)
        except TypeError:
            continue
    return client.read_holding_registers(addr, count)


client = ModbusTcpClient(IP, port=PORT, timeout=2)
if not client.connect():
    sys.exit(f"[!] Tidak bisa terhubung ke PLC {IP}:{PORT} (cek kabel/IP/port, ping {IP})")
print(f"[OK] Terhubung ke PLC {IP}:{PORT} (unit {UNIT})")

if len(sys.argv) >= 2 and sys.argv[1] == "--scan":
    a = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    r = baca(client, a, n)
    if r.isError():
        sys.exit(f"[!] Gagal membaca register {a}..{a + n - 1}: {r}")
    for i, v in enumerate(r.registers):
        print(f"  register {a + i:5d} = {v}")
    client.close()
    sys.exit(0)

print(f"Membaca State di register {REG_STATE}"
      + (f" dan PbCounter di register {REG_PB}" if REG_PB >= 0 else "")
      + "  (Ctrl+C untuk berhenti)")
try:
    while True:
        r = baca(client, REG_STATE)
        teks = f"State = {r.registers[0]}" if not r.isError() else f"ERROR {r}"
        if REG_PB >= 0:
            p = baca(client, REG_PB)
            teks += f" | PbCounter = {p.registers[0]}" if not p.isError() else " | PbCounter ERROR"
        print(f"\r{teks}      ", end="", flush=True)
        time.sleep(0.5)
except KeyboardInterrupt:
    print()
finally:
    client.close()
