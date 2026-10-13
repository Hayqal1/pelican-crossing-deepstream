# Pelican Crossing — Jetson Orin Nano 4GB (JetPack 7.2.1)

Deteksi pelanggaran Pelican Crossing (person, motorcycle, car, bus, truck) dengan
DeepStream 9.1 + YOLO26n (`yolo26.engine`) + PLC Modbus TCP.

| Komponen | Versi |
|---|---|
| JetPack / L4T | 7.2.1 / 39.2.1, Ubuntu 24.04 |
| DeepStream | 9.1 |
| CUDA / TensorRT | 13.2 / 10.16 |
| Python | 3.12 (virtualenv `~/ds-venv`: pyds, numpy 1.26.4, pymodbus) |

Model `models/yolo26n.onnx` sudah disertakan (sudah diverifikasi). Engine `yolo26.engine`
dibangun di Jetson oleh installer (engine TensorRT tidak bisa disalin dari PC/laptop).

---

## 1. Persiapan

1. Flash **JetPack 7.2.1** ke Orin Nano (JetPack ISO lewat USB atau SDK Manager — tidak ada image SD card untuk JetPack 7.2).
2. Sambungkan Jetson ke internet dan ke jaringan kamera/PLC.
3. Unduh **`deepstream-9.1_9.1.0-1_arm64.deb`** (DeepStream SDK, versi Jetson) dari halaman DeepStream NVIDIA,
   taruh di `~/Downloads` atau di folder proyek ini.
4. Salin zip ini ke Jetson, lalu:
   ```bash
   unzip deepstream_pelican_crossing_jetson.zip
   cd deepstream_pelican_crossing_jetson
   chmod +x setup_jetson.sh run.sh scripts/*.sh
   ```

## 2. Instalasi (satu perintah)

```bash
TANPA_GUI=1 bash setup_jetson.sh
```
(`TANPA_GUI=1` mematikan desktop mulai boot berikutnya agar RAM cukup. Hilangkan jika masih butuh desktop.)

Tahap yang dijalankan otomatis:

| Tahap | Isi | Perkiraan waktu |
|---|---|---|
| `cek` | Cek JetPack, RAM, disk, trtexec | < 1 menit |
| `optimasi` | Mode daya MAXN, swap 6GB | < 1 menit |
| `deepstream` | Prasyarat + DeepStream 9.1 dari file .deb | 5–10 menit |
| `pyds` | gst-python + build **pyds** + numpy 1.26.4 + pymodbus | 20–40 menit |
| `parser` | Compile parser YOLO (DeepStream-Yolo, CUDA 13.2) | 2–5 menit |
| `engine` | Build **`yolo26.engine`** (FP16, batch 2) dengan trtexec | 10–30 menit |
| `verifikasi` | Cek semua komponen | < 1 menit |

Jika satu tahap gagal, perbaiki lalu lanjutkan dari tahap itu, mis.:
```bash
bash setup_jetson.sh --dari parser
```
Menjalankan satu tahap saja: `bash setup_jetson.sh engine`. Log lengkap: `setup_jetson.log`.

Setelah selesai, reboot sekali (agar mode daya & mode tanpa desktop aktif):
```bash
sudo reboot
```

## 3. Tes

```bash
cd ~/deepstream_pelican_crossing_jetson
bash scripts/cek_sistem.sh
bash scripts/tes_kamera.sh
~/ds-venv/bin/python3 scripts/tes_plc.py           # Ctrl+C untuk berhenti
HEADLESS=1 PLC_STATE=4 ./run.sh                    # uji logika tanpa PLC
```

## 4. Menjalankan

```bash
sudo jetson_clocks
HEADLESS=1 ./run.sh
```
Pelanggaran tercetak di terminal dan tersimpan di `logs/pelanggaran_YYYY-MM-DD.csv`.

Autostart saat boot:
```bash
bash scripts/pasang_service.sh
journalctl -u pelican-crossing -f
```

## 5. Pengaturan

- **Kamera**: `RTSP_KAM1` / `RTSP_KAM2` di `pelican_deepstream.py`
  (saat ini `192.168.100.102/stream1` dan `192.168.100.101`), atau timpa lewat environment variable.
- **PLC**: `PLC_IP`, `PLC_PORT`, `PLC_UNIT`, `PLC_REG_STATE`, `PLC_REG_PBCOUNTER` (lihat bagian atas
  `pelican_deepstream.py`). Cari alamat register dengan `~/ds-venv/bin/python3 scripts/tes_plc.py --scan 0 20`.
- **Zona ZEBRA & garis STOPLINE**: `config_nvdsanalytics.txt` (resolusi 720×360).
  Ambil gambar acuan: `bash scripts/snapshot_kamera.sh`.
- **Beban GPU**: `interval=1` di `config_infer_yolo26.txt` (deteksi tiap 2 frame). Pantau dengan `sudo tegrastats`.

## 6. Troubleshooting

| Gejala | Solusi |
|---|---|
| `deepstream-9.1...deb tidak ditemukan` | Unduh file .deb, taruh di `~/Downloads`, lalu `bash setup_jetson.sh --dari deepstream` |
| Build pyds `Killed` | Swap belum aktif / RAM penuh: `free -h`, tutup aplikasi, `JOBS=1 bash setup_jetson.sh pyds` |
| Compile parser gagal | Cek `ls -d /usr/local/cuda*`, lalu `CUDA_VER=13.2 bash setup_jetson.sh parser`; kirim error bila tetap gagal |
| Build engine gagal / `Killed` | `WORKSPACE=512 bash setup_jetson.sh engine` |
| `Deserialize engine failed` | Engine dari perangkat/JetPack lain: `ULANG=1 bash setup_jetson.sh engine` |
| `No module named pyds` saat run | Program harus dijalankan lewat `./run.sh` (memakai `~/ds-venv`) |
| `PLC[PUTUS]` | `ping 192.168.200.100`, cek port 502, jalankan `tes_plc.py` |
| FPS rendah | `sudo jetson_clocks`, cek `sudo nvpmodel -q` (MAXN), gunakan sub-stream kamera |
