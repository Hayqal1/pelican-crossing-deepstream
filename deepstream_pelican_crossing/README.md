# Deteksi Pelanggaran Pelican Crossing — DeepStream + YOLO26n + PLC

Mendeteksi **orang, motor, mobil, bus, truk** dari 2 kamera RTSP dan mencatat pelanggaran
sesuai flowchart *Sistem Pellican Crossing FIX*, dengan state lampu dibaca dari PLC (Modbus TCP).

```
Kamera RTSP x2 ─► nvurisrcbin ─► nvstreammux (720x360) ─► nvinfer YOLO26n (5 kelas)
   ─► nvtracker (NvDCF) ─► nvdsanalytics (ROI ZEBRA + garis STOPLINE)
   ─► probe: aturan pelanggaran × State PLC ─► log terminal + CSV (+ tampilan OSD)
                                    ▲
                     PLC Modbus TCP 192.168.200.100:502
```

---

## 1. Aturan pelanggaran (dari flowchart)

| State | Nama | Lampu kendaraan | Lampu pejalan | Cek pejalan | Cek kendaraan |
|---|---|---|---|---|---|
| 0 | Normal | Kuning | Merah | ✅ | — |
| 1 | Stand By | Hijau | Merah | ✅ | — |
| 2 | Stand By Yellow | Kuning | Merah | ✅ | — |
| 3 | All Red 1 | Merah | Merah | ✅ | ✅ |
| 4 | Crossing | Merah | **Hijau** | — | ✅ |
| 5 | All Red 2 | Merah | Merah | ✅ | ✅ |
| 6 | Wait For Normal | Hijau | Merah | ✅ | — |

- **PedestrianCrossingViolation**: `person` berada di dalam zona **ZEBRA** saat lampu pejalan merah.
- **TrafficViolation**: `motorcycle / car / bus / truck` melintasi garis **STOPLINE** saat lampu kendaraan merah.
- **PedestrianButtonViolation**: tombol ditekan lebih dari 1× dalam satu siklus (dicek saat State 5 → 6).
  Butuh alamat register `PbCounter` dari PLC (lihat bagian 6).

Setiap objek (track ID) hanya dicatat **sekali** per jenis pelanggaran. Kotak objek pelanggar
menjadi **merah** dengan label `[VIOLATION]`, yang lain hijau.

---

## 2. Isi paket

| File | Fungsi |
|---|---|
| `pelican_deepstream.py` | Program utama (IP kamera & PLC tidak diubah) |
| `config_infer_yolo26.txt` | YOLO26n, hanya 5 kelas: person, car, motorcycle, bus, truck |
| `config_nvdsanalytics.txt` | Zona ZEBRA & garis STOPLINE per kamera (**wajib disesuaikan**) |
| `run.sh` | Menjalankan program |
| `scripts/1_install_deps.sh` | Paket sistem, `pymodbus`, `pyds` |
| `scripts/2_export_yolo26n.sh` | Unduh & export YOLO26n → `models/yolo26n.onnx` |
| `scripts/3_build_parser.sh` | Compile parser YOLO (DeepStream-Yolo) |
| `scripts/cek_sistem.sh` | Cek kesiapan |
| `scripts/tes_kamera.sh` | Tes RTSP tanpa AI |
| `scripts/tes_plc.py` | Tes koneksi & isi register PLC |
| `scripts/snapshot_kamera.sh` | Ambil gambar 720×360 untuk menentukan koordinat |
| `pelican-crossing.service` | Template autostart saat boot |

---

## 3. Instalasi

### Jika proyek `deepstream_yolo26_counter` sudah jalan di laptop ini (cara cepat)

Model, parser, dan engine bisa dipakai ulang — tidak perlu export/build lagi:
```bash
cd ~/Downloads
unzip deepstream_pelican_crossing.zip
cd deepstream_pelican_crossing
chmod +x run.sh scripts/*.sh

cp -r ../deepstream_yolo26_counter/models .
cp -r ../deepstream_yolo26_counter/DeepStream-Yolo .
cp ../deepstream_yolo26_counter/model_b2_gpu0_fp16.engine .

pip3 install pymodbus || pip3 install --break-system-packages pymodbus
bash scripts/cek_sistem.sh
```

### Instalasi dari nol
```bash
unzip deepstream_pelican_crossing.zip && cd deepstream_pelican_crossing
chmod +x run.sh scripts/*.sh
bash scripts/1_install_deps.sh
bash scripts/2_export_yolo26n.sh
bash scripts/3_build_parser.sh
bash scripts/cek_sistem.sh
```
Run pertama membangun engine TensorRT (±5 menit di laptop RTX, 10–30 menit di Jetson).

---

## 4. Tes kamera & PLC

```bash
bash scripts/tes_kamera.sh        # kedua kamera harus "stream berjalan"
python3 scripts/tes_plc.py        # harus "[OK] Terhubung" lalu menampilkan State
```

---

## 5. Atur zona ZEBRA & garis STOPLINE (wajib)

Koordinat di `config_nvdsanalytics.txt` memakai resolusi **720×360** dan saat ini masih contoh.

1. Ambil gambar dari tiap kamera:
   ```bash
   bash scripts/snapshot_kamera.sh      # -> snapshot/kam1.jpg, snapshot/kam2.jpg
   ```
2. Buka gambar di GIMP/Pinta, arahkan kursor ke titik-titik berikut dan catat koordinat x,y:
   - **ZEBRA**: 4 sudut area zebra cross, berurutan mengelilingi area.
   - **STOPLINE**: 2 ujung garis henti kendaraan, plus 2 titik arah datang kendaraan
     (titik awal sebelum garis → titik akhir sesudah garis).
3. Isi ke config:
   ```ini
   [roi-filtering-stream-0]            ; KAM1
   roi-ZEBRA=x1;y1;x2;y2;x3;y3;x4;y4

   [line-crossing-stream-0]
   line-crossing-STOPLINE=dx1;dy1;dx2;dy2;lx1;ly1;lx2;ly2
   ```
   Ulangi untuk `stream-1` (KAM2). **Nama `ZEBRA` dan `STOPLINE` jangan diganti** (dipakai di kode).
4. Jalankan dengan tampilan untuk memastikan zona & garis berada di tempat yang benar.

---

## 6. Pengaturan PLC

Default: IP `192.168.200.100`, port `502`, State dibaca dari holding register alamat `0`.
Semua bisa diubah **tanpa mengedit kode**:

| Variabel | Default | Keterangan |
|---|---|---|
| `PLC_IP` | 192.168.200.100 | IP PLC |
| `PLC_PORT` | 502 | Port Modbus TCP |
| `PLC_UNIT` | 1 | Slave / unit ID |
| `PLC_REG_STATE` | 0 | Alamat register **State** (0–6) |
| `PLC_REG_PBCOUNTER` | -1 (mati) | Alamat register **PbCounter** (untuk pelanggaran tombol) |
| `PLC_STATE` | — | Uji tanpa PLC: state dipaku ke nilai ini |

> ⚠️ **Perhatikan alamat register.** Di flowchart, `D0` ditulis sebagai *"Data Register to store
> the number of pushes"* (PbCounter), sedangkan kode awal membaca D0 sebagai **State**. Pastikan
> di program PLC register mana yang berisi State dan mana PbCounter. Cari dengan:
> ```bash
> python3 scripts/tes_plc.py --scan 0 20     # tampilkan register 0..19, tekan tombol & amati
> ```
> Alamat Modbus untuk D0 berbeda tiap merek PLC (mis. Delta DVP: D0 = 4096; banyak PLC lain: 0).

Contoh: State di register 1, PbCounter di register 0:
```bash
PLC_REG_STATE=1 PLC_REG_PBCOUNTER=0 ./run.sh
```

---

## 7. Menjalankan

```bash
./run.sh                    # dengan tampilan (laptop dengan monitor)
HEADLESS=1 ./run.sh         # tanpa tampilan
LOG=1 ./run.sh              # simpan juga output terminal ke logs/
PLC_STATE=4 ./run.sh        # UJI TANPA PLC: paksa State 4 (kendaraan merah)
PLC_STATE=0 ./run.sh        # UJI TANPA PLC: paksa State 0 (pejalan merah)
```

Contoh keluaran:
```
[2026-10-12 13:20:01] [PLC] State 3 -> 4: Crossing (Vehicle Red, Ped Green)
[2026-10-12 13:20:05] [PELANGGARAN KENDARAAN | State 4] [KAM1] #31 motorcycle menerobos lampu merah! (Garis: STOPLINE) | Total Kendaraan: 1
[2026-10-12 13:21:40] [PELANGGARAN PEJALAN | State 1] [KAM2] #58 person menyeberang saat lampu pejalan merah! | Total Pejalan: 1
[STATUS] KAM1: 25.0 FPS | KAM2: 25.0 FPS | PLC[OK] State 0 (Normal ...) | Pejalan: 1 | Kendaraan: 1 | Tombol: 0
```
Semua pelanggaran juga tersimpan di **`logs/pelanggaran_YYYY-MM-DD.csv`** (bisa dibuka di Excel).
`PLC[PUTUS]` artinya PLC tidak terbaca — program tetap jalan memakai state terakhir.

---

## 8. Laptop dengan 2 GPU (Intel + NVIDIA)

Program otomatis memaksa tampilan lewat GPU NVIDIA. Jika jendela video tetap error
(`cuGraphicsGLRegisterBuffer ... 219`): `sudo prime-select nvidia` lalu reboot, atau login dengan
sesi **"Ubuntu on Xorg"**. Deteksi tetap jalan normal dengan `HEADLESS=1`.

---

## 9. Autostart saat boot

```bash
sed -e "s|__USER__|$USER|" -e "s|__DIR__|$PWD|" pelican-crossing.service \
  | sudo tee /etc/systemd/system/pelican-crossing.service
sudo systemctl daemon-reload
sudo systemctl enable --now pelican-crossing
journalctl -u pelican-crossing -f
```
Atur alamat register PLC lewat baris `Environment=` di file service.

---

## 10. Troubleshooting

| Gejala | Solusi |
|---|---|
| `PLC[PUTUS]` terus | `ping 192.168.200.100`, lalu `python3 scripts/tes_plc.py`. Cek port 502 & unit ID |
| State selalu 0 | Alamat register salah → `python3 scripts/tes_plc.py --scan 0 20` |
| `pymodbus belum terpasang` | `pip3 install pymodbus` (Ubuntu 24.04: tambah `--break-system-packages`) |
| Tidak ada pelanggaran tercatat | Zona/garis belum sesuai; uji dengan `PLC_STATE=4` dan lihat tampilan |
| Pelanggaran pejalan berlebihan | Zona ZEBRA terlalu luas (mencakup trotoar) — persempit |
| Objek lain (sepeda, dll.) terdeteksi | Cek `filter-out-class-ids` di `config_infer_yolo26.txt` |
| Engine dibangun ulang tiap run | Pastikan `model_b2_gpu0_fp16.engine` ada di folder proyek |
| `Decoder bukan NVMM` | Set codec kamera ke H.264/H.265 standar |
