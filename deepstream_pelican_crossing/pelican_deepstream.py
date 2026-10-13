#!/usr/bin/env python3
"""
DeepStream Pelican Crossing Violation Detection System
Penggabungan arsitektur NVIDIA DeepStream SDK dengan logika Pelican Crossing
(flowchart "Sistem Pellican Crossing FIX").
Komunikasi State PLC via Modbus TCP.

Deteksi  : person, motorcycle, car, bus, truck (YOLO26n)
Pelanggaran:
  - PedestrianCrossingViolation : orang berada di zona zebra (ROI "ZEBRA")
                                  saat lampu pejalan MERAH  (State 0,1,2,3,5,6)
  - TrafficViolation            : kendaraan melewati garis stop (garis "STOPLINE")
                                  saat lampu kendaraan MERAH (State 3,4,5)
  - PedestrianButtonViolation   : tombol ditekan lebih dari 1x dalam satu siklus
                                  (dicek saat State 5 -> 6, butuh register PbCounter)
"""

import os
import sys
import csv
import time
import datetime
import threading

import gi
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst
import pyds

# ==============================================================================
# 1. KONFIGURASI STREAM & FILE PATH
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SUMBER = [
    os.environ.get("RTSP_KAM1", "rtsp://admin:GANTI_PASSWORD@192.168.100.109"),
    os.environ.get("RTSP_KAM2", "rtsp://admin:GANTI_PASSWORD@192.168.100.1010/"),
]

MUX_W, MUX_H = 720, 360  # Disesuaikan dengan resolusi BatchDetec.py (sama dengan config_nvdsanalytics.txt)
CONFIG_INFER = os.path.join(BASE_DIR, "config_infer_yolo26.txt")
CONFIG_ANALYTICS = os.path.join(BASE_DIR, "config_nvdsanalytics.txt")
TRACKER_LIB = "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so"
TRACKER_CFG = "/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml"
TAMPILKAN = bool(os.environ.get("DISPLAY"))   # Otomatis mati saat mode SSH headless
LOG_DIR = os.path.join(BASE_DIR, "logs")

INTERVAL_STATUS = 10                          # Detik untuk status log berkala
N = len(SUMBER)

# Nama zona & garis di config_nvdsanalytics.txt
ZONA_ZEBRA = "ZEBRA"        # roi-ZEBRA      : area zebra cross (pejalan kaki)
GARIS_STOP = "STOPLINE"     # line-crossing-STOPLINE : garis henti kendaraan

# ==============================================================================
# 2. KONFIGURASI PLC (bisa diubah lewat environment variable tanpa edit kode)
# ==============================================================================
PLC_IP = os.environ.get("PLC_IP", "192.168.200.100")
PLC_PORT = int(os.environ.get("PLC_PORT", "502"))
PLC_UNIT = int(os.environ.get("PLC_UNIT", "1"))                    # Modbus slave/unit id
PLC_REG_STATE = int(os.environ.get("PLC_REG_STATE", "0"))          # alamat holding register State
PLC_REG_PBCOUNTER = int(os.environ.get("PLC_REG_PBCOUNTER", "-1")) # alamat PbCounter, -1 = tidak dibaca
PLC_STATE_MANUAL = os.environ.get("PLC_STATE")                     # uji tanpa PLC, mis. PLC_STATE=4


# ==============================================================================
# 3. THREAD KOMUNIKASI MODBUS PLC
# ==============================================================================
class PLCModbusThread:
    """
    Thread non-blocking untuk membaca State Machine Pelican Crossing (dan PbCounter)
    dari PLC via Modbus TCP secara real-time.
    """
    def __init__(self, ip, port=502, unit=1, reg_state=0, reg_pbcounter=-1,
                 interval=0.05, state_manual=None):
        self.ip = ip
        self.port = port
        self.unit = unit
        self.reg_state = reg_state
        self.reg_pbcounter = reg_pbcounter
        self.interval = interval
        self.manual = state_manual is not None
        self.current_state = int(state_manual) if self.manual else 0
        self.pbcounter = 0
        self.connected = False
        self.running = True
        self.lock = threading.Lock()
        self.on_state_change = None   # callback(state_lama, state_baru, pb_max)
        self._pb_max = 0

        if not self.manual:
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()

    def _baca(self, client, addr, count=1):
        # Kompatibel pymodbus 2.x / 3.x (argumen slave/unit/device_id berubah antar versi)
        for kw in ({"count": count, "device_id": self.unit},
                   {"count": count, "slave": self.unit},
                   {"count": count, "unit": self.unit},
                   {"count": count}):
            try:
                return client.read_holding_registers(addr, **kw)
            except TypeError:
                continue
        return client.read_holding_registers(addr, count)

    def _read_loop(self):
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError:
            try:
                from pymodbus.client.sync import ModbusTcpClient   # pymodbus 2.x
            except ImportError:
                print("[!] Library 'pymodbus' belum terpasang (pip3 install pymodbus).")
                print("[!] Menggunakan default State 0.")
                return

        client = ModbusTcpClient(self.ip, port=self.port, timeout=1)
        print(f"[*] Menghubungkan Modbus PLC di {self.ip}:{self.port}...", flush=True)
        sudah_lapor_putus = False

        while self.running:
            try:
                if not self.connected:
                    self.connected = bool(client.connect())
                if self.connected:
                    rs = self._baca(client, self.reg_state)
                    if rs is None or rs.isError():
                        raise IOError("gagal baca register State")
                    state_baru = int(rs.registers[0])

                    pb = None
                    if self.reg_pbcounter >= 0:
                        rp = self._baca(client, self.reg_pbcounter)
                        if rp is not None and not rp.isError():
                            pb = int(rp.registers[0])

                    self._update(state_baru, pb)
                    if sudah_lapor_putus:
                        print("[*] Koneksi PLC tersambung kembali", flush=True)
                        sudah_lapor_putus = False
            except Exception as e:
                if self.connected or not sudah_lapor_putus:
                    print(f"[!] PLC tidak terbaca ({e}). Mencoba lagi...", flush=True)
                    sudah_lapor_putus = True
                self.connected = False
                try:
                    client.close()
                except Exception:
                    pass
                time.sleep(1)

            time.sleep(self.interval)

        client.close()

    def _update(self, state_baru, pb):
        with self.lock:
            state_lama = self.current_state
            if pb is not None:
                self.pbcounter = pb
                if state_baru != 6:
                    self._pb_max = max(self._pb_max, pb)
            self.current_state = state_baru
            pb_max = self._pb_max
            if state_baru != state_lama and state_baru == 6:
                self._pb_max = 0
        if state_baru != state_lama and self.on_state_change:
            self.on_state_change(state_lama, state_baru, pb_max)

    def get_state(self):
        with self.lock:
            return self.current_state

    def status_koneksi(self):
        if self.manual:
            return "MANUAL"
        return "OK" if self.connected else "PUTUS"

    def stop(self):
        self.running = False
        if hasattr(self, "thread"):
            self.thread.join(timeout=2)


# ==============================================================================
# 4. ATURAN PELANGGARAN PELICAN CROSSING (SESUAI FLOWCHART PDF)
# ==============================================================================
KELAS_PEJALAN = {"person"}
KELAS_KENDARAAN = {"car", "motorcycle", "bus", "truck"}
KELAS_DIPANTAU = KELAS_PEJALAN | KELAS_KENDARAAN

PLC_STATE_DESC = {
    0: "Normal (Vehicle Yellow, Ped Red)",
    1: "Stand By (Vehicle Green, Ped Red)",
    2: "Stand By Yellow (Vehicle Yellow, Ped Red)",
    3: "All Red 1 (Vehicle Red, Ped Red)",
    4: "Crossing (Vehicle Red, Ped Green)",
    5: "All Red 2 (Vehicle Red, Ped Red)",
    6: "Wait For Normal (Vehicle Green, Ped Red)",
}

# State -> (cek PedestrianCrossingViolation, cek TrafficViolation)
# Diturunkan dari flowchart: setiap transisi state diikuti pengecekan pelanggaran.
#   ->1, ->2, ->6, ->0 : cek pejalan
#   ->3, ->5           : cek pejalan + kendaraan (All Red, semua lampu merah)
#   ->4                : cek kendaraan (pejalan hijau, kendaraan merah)
ATURAN_STATE = {
    0: (True, False),
    1: (True, False),
    2: (True, False),
    3: (True, True),
    4: (False, True),
    5: (True, True),
    6: (True, False),
}


def cek_pelanggaran_pelican(plc_state, obj_label, di_zebra, lewat_garis_stop):
    """
    Return (apakah_pelanggar, tipe):
    - PEJALAN_KAKI : person di zona ZEBRA saat lampu pejalan merah
    - KENDARAAN    : kendaraan melewati STOPLINE saat lampu kendaraan merah
    """
    cek_pejalan, cek_kendaraan = ATURAN_STATE.get(plc_state, (False, False))
    if obj_label in KELAS_PEJALAN and cek_pejalan and di_zebra:
        return True, "PEJALAN_KAKI"
    if obj_label in KELAS_KENDARAAN and cek_kendaraan and lewat_garis_stop:
        return True, "KENDARAAN"
    return False, None


# ==============================================================================
# 5. DATA PENGHITUNG PELANGGARAN, LOG CSV & METRIK PERFORMA
# ==============================================================================
id_sudah_dicatat = set()          # (sid, track_id, tipe)
total_pelanggaran_kendaraan = 0
total_pelanggaran_pejalan = 0
total_pelanggaran_tombol = 0

jumlah_frame = {i: 0 for i in range(N)}
frame_lalu = {i: 0 for i in range(N)}
waktu_lalu = time.time()
fps_kamera = {i: 0.0 for i in range(N)}

META_OBJ = None
csv_lock = threading.Lock()


def catat_csv(tipe, sid, state, track_id="", label="", info=""):
    os.makedirs(LOG_DIR, exist_ok=True)
    now = datetime.datetime.now()
    path = os.path.join(LOG_DIR, f"pelanggaran_{now:%Y-%m-%d}.csv")
    baru = not os.path.exists(path)
    with csv_lock, open(path, "a", newline="") as f:
        w = csv.writer(f)
        if baru:
            w.writerow(["waktu", "tipe", "kamera", "state_plc", "track_id", "kelas", "info"])
        w.writerow([now.strftime("%Y-%m-%d %H:%M:%S"), tipe,
                    f"KAM{sid + 1}" if sid is not None else "-", state, track_id, label, info])


def saat_state_berubah(state_lama, state_baru, pb_max):
    """Dipanggil thread PLC. PedestrianButtonViolation: State 5 -> 6 dengan PbCounter > 1."""
    global total_pelanggaran_tombol
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [PLC] State {state_lama} -> {state_baru}: "
          f"{PLC_STATE_DESC.get(state_baru, '?')}", flush=True)
    if state_lama == 5 and state_baru == 6 and PLC_REG_PBCOUNTER >= 0 and pb_max > 1:
        total_pelanggaran_tombol += 1
        print(f"[{now}] [PELANGGARAN TOMBOL] Tombol ditekan {pb_max}x dalam satu siklus | "
              f"Total Tombol: {total_pelanggaran_tombol}", flush=True)
        catat_csv("TOMBOL", None, state_baru, info=f"PbCounter={pb_max}")


plc_modbus = PLCModbusThread(ip=PLC_IP, port=PLC_PORT, unit=PLC_UNIT,
                             reg_state=PLC_REG_STATE, reg_pbcounter=PLC_REG_PBCOUNTER,
                             interval=0.05, state_manual=PLC_STATE_MANUAL)
plc_modbus.on_state_change = saat_state_berubah


def iter_list(l):
    while l is not None:
        yield l.data
        try:
            l = l.next
        except StopIteration:
            break


# ==============================================================================
# 6. PROBE FUNCTION (EVALUASI PELANGGARAN PADA METADATA DEEPSTREAM)
# ==============================================================================
def probe_analytics(pad, info, u_data):
    global total_pelanggaran_kendaraan, total_pelanggaran_pejalan

    buf = info.get_buffer()
    if not buf:
        return Gst.PadProbeReturn.OK

    state_plc = plc_modbus.get_state()

    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(buf))
    for data in iter_list(batch_meta.frame_meta_list):
        frame_meta = pyds.NvDsFrameMeta.cast(data)
        sid = frame_meta.pad_index
        jumlah_frame[sid] += 1

        for odata in iter_list(frame_meta.obj_meta_list):
            obj_meta = pyds.NvDsObjectMeta.cast(odata)
            track_id = obj_meta.object_id
            obj_label = obj_meta.obj_label
            if obj_label not in KELAS_DIPANTAU:
                continue

            # Status zona/garis dari nvdsanalytics
            di_zebra, lewat_garis_stop, arah = False, False, ""
            for udata in iter_list(obj_meta.obj_user_meta_list):
                user_meta = pyds.NvDsUserMeta.cast(udata)
                if user_meta.base_meta.meta_type != META_OBJ:
                    continue
                oinfo = pyds.NvDsAnalyticsObjInfo.cast(user_meta.user_meta_data)
                if ZONA_ZEBRA in list(oinfo.roiStatus):
                    di_zebra = True
                lc = list(oinfo.lcStatus)
                if GARIS_STOP in lc:
                    lewat_garis_stop = True
                    arah = ",".join(lc)

            apakah_pelanggar, tipe = cek_pelanggaran_pelican(
                state_plc, obj_label, di_zebra, lewat_garis_stop)

            if apakah_pelanggar:
                kunci = (sid, track_id, tipe)
                if kunci not in id_sudah_dicatat:
                    id_sudah_dicatat.add(kunci)
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if tipe == "KENDARAAN":
                        total_pelanggaran_kendaraan += 1
                        print(f"[{now}] [PELANGGARAN KENDARAAN | State {state_plc}] [KAM{sid + 1}] "
                              f"#{track_id} {obj_label} menerobos lampu merah! (Garis: {arah}) | "
                              f"Total Kendaraan: {total_pelanggaran_kendaraan}", flush=True)
                    else:
                        total_pelanggaran_pejalan += 1
                        print(f"[{now}] [PELANGGARAN PEJALAN | State {state_plc}] [KAM{sid + 1}] "
                              f"#{track_id} {obj_label} menyeberang saat lampu pejalan merah! | "
                              f"Total Pejalan: {total_pelanggaran_pejalan}", flush=True)
                    catat_csv(tipe, sid, state_plc, track_id, obj_label)

            # Warnai Bounding Box di OSD: Merah untuk Pelanggar, Hijau untuk Tertib
            tercatat = any((sid, track_id, t) in id_sudah_dicatat for t in ("KENDARAAN", "PEJALAN_KAKI"))
            if tercatat:
                obj_meta.rect_params.border_color.set(1.0, 0.0, 0.0, 1.0)
                obj_meta.text_params.display_text = f"#{track_id} {obj_label} [VIOLATION]"
                obj_meta.text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
                obj_meta.text_params.set_bg_clr = 1
                obj_meta.text_params.text_bg_clr.set(0.8, 0.0, 0.0, 0.8)
            else:
                obj_meta.rect_params.border_color.set(0.0, 1.0, 0.0, 1.0)
                obj_meta.text_params.display_text = f"#{track_id} {obj_label}"

        # Banner Info OSD di atas frame video
        if TAMPILKAN:
            display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
            display_meta.num_labels = 1
            text_params = display_meta.text_params[0]

            desc_state = PLC_STATE_DESC.get(state_plc, f"State {state_plc}")
            fps_val = int(fps_kamera.get(sid, 0.0))
            text_params.display_text = (
                f"KAM{sid + 1} | PLC[{plc_modbus.status_koneksi()}] State {state_plc}: {desc_state}\n"
                f"Pejalan: {total_pelanggaran_pejalan} | Kendaraan: {total_pelanggaran_kendaraan} | "
                f"Tombol: {total_pelanggaran_tombol} | FPS: {fps_val}")
            text_params.x_offset = 10
            text_params.y_offset = 10
            text_params.font_params.font_name = "Sans"
            text_params.font_params.font_size = 9
            text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
            text_params.set_bg_clr = 1

            if state_plc == 4:
                text_params.text_bg_clr.set(0.7, 0.0, 0.0, 0.85)   # Merah: waktu menyeberang
            elif state_plc in (3, 5):
                text_params.text_bg_clr.set(0.4, 0.4, 0.4, 0.85)   # Abu-abu: All Red
            else:
                text_params.text_bg_clr.set(0.0, 0.5, 0.0, 0.85)   # Hijau: kendaraan jalan

            pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)

    return Gst.PadProbeReturn.OK


# ==============================================================================
# 7. CETAK STATUS BERKALA (FPS & TOTAL VIOLATIONS)
# ==============================================================================
def cetak_status():
    global waktu_lalu
    sekarang = time.time()
    dt = max(1e-6, sekarang - waktu_lalu)
    bagian = []
    for i in range(N):
        fps = (jumlah_frame[i] - frame_lalu[i]) / dt
        frame_lalu[i] = jumlah_frame[i]
        fps_kamera[i] = fps
        bagian.append(f"KAM{i + 1}: {fps:.1f} FPS")
    waktu_lalu = sekarang

    state_plc = plc_modbus.get_state()
    desc_state = PLC_STATE_DESC.get(state_plc, f"State {state_plc}")

    print(f"[STATUS] {' | '.join(bagian)} | PLC[{plc_modbus.status_koneksi()}] "
          f"State {state_plc} ({desc_state}) | "
          f"Pejalan: {total_pelanggaran_pejalan} | Kendaraan: {total_pelanggaran_kendaraan} | "
          f"Tombol: {total_pelanggaran_tombol}", flush=True)
    return True


# ==============================================================================
# 8. KONSTRUKSI PIPELINE GSTREAMER / DEEPSTREAM
# ==============================================================================
def cb_newpad(srcbin, pad, source_bin):
    caps = pad.get_current_caps() or pad.query_caps(None)
    struct = caps.get_structure(0)
    if not struct.get_name().startswith("video"):
        return
    if caps.get_features(0).contains("memory:NVMM"):
        if not source_bin.get_static_pad("src").set_target(pad):
            sys.stderr.write("[!] Gagal menghubungkan pad sumber\n")
    else:
        sys.stderr.write("[!] Decoder bukan NVMM (hardware decode tidak aktif)\n")


def buat_source_bin(index, uri):
    nbin = Gst.Bin.new(f"source-bin-{index}")
    src = Gst.ElementFactory.make("nvurisrcbin", f"uri-src-{index}")
    if not src:
        sys.exit("[!] nvurisrcbin tidak ditemukan. Pastikan DeepStream SDK terpasang.")
    src.set_property("uri", uri)
    src.set_property("rtsp-reconnect-interval", 10)
    src.set_property("latency", 200)
    src.set_property("select-rtp-protocol", 4)
    try:
        src.set_property("disable-audio", True)
    except TypeError:
        pass
    src.connect("pad-added", cb_newpad, nbin)
    nbin.add(src)
    nbin.add_pad(Gst.GhostPad.new_no_target("src", Gst.PadDirection.SRC))
    return nbin


def buat(factory, nama):
    el = Gst.ElementFactory.make(factory, nama)
    if not el:
        sys.exit(f"[!] Gagal membuat elemen {factory}")
    return el


def minta_pad(mux, nama):
    fn = getattr(mux, "request_pad_simple", None) or mux.get_request_pad
    return fn(nama)


def bus_call(bus, message, loop):
    t = message.type
    if t == Gst.MessageType.EOS:
        print("[*] Stream selesai (EOS)")
        loop.quit()
    elif t == Gst.MessageType.WARNING:
        err, _ = message.parse_warning()
        print(f"[WARN] {err}")
    elif t == Gst.MessageType.ERROR:
        err, dbg = message.parse_error()
        print(f"[ERROR] {err}\n{dbg}")
        loop.quit()
    return True


def pakai_gpu_nvidia_untuk_tampilan():
    """Laptop 2 GPU (Intel + NVIDIA): paksa tampilan lewat GPU NVIDIA.
    Mencegah error 'cuGraphicsGLRegisterBuffer failed with error(219)'."""
    if os.path.exists("/etc/nv_tegra_release"):   # Jetson tidak perlu
        return
    egl_nvidia = "/usr/share/glvnd/egl_vendor.d/10_nvidia.json"
    if os.path.isfile(egl_nvidia):
        os.environ.setdefault("__EGL_VENDOR_LIBRARY_FILENAMES", egl_nvidia)
    os.environ.setdefault("__NV_PRIME_RENDER_OFFLOAD", "1")
    os.environ.setdefault("__GLX_VENDOR_LIBRARY_NAME", "nvidia")


# ==============================================================================
# 9. MAIN ENTRYPOINT
# ==============================================================================
def main():
    global META_OBJ
    if TAMPILKAN:
        pakai_gpu_nvidia_untuk_tampilan()
    Gst.init(None)
    for f in (CONFIG_INFER, CONFIG_ANALYTICS):
        if not os.path.isfile(f):
            sys.exit(f"[!] File config tidak ditemukan: {f}")

    META_OBJ = pyds.nvds_get_user_meta_type("NVIDIA.DSANALYTICSOBJ.USER_META")

    pipeline = Gst.Pipeline()

    # 1. Stream Muxer
    mux = buat("nvstreammux", "mux")
    mux.set_property("batch-size", N)
    mux.set_property("width", MUX_W)
    mux.set_property("height", MUX_H)
    mux.set_property("batched-push-timeout", 40000)
    mux.set_property("live-source", 1)
    pipeline.add(mux)

    # 2. Source Bins (RTSP Sources)
    for i, uri in enumerate(SUMBER):
        sb = buat_source_bin(i, uri)
        pipeline.add(sb)
        sb.get_static_pad("src").link(minta_pad(mux, f"sink_{i}"))

    # 3. Primary GIE (YOLO26n via TensorRT Engine)
    pgie = buat("nvinfer", "pgie")
    pgie.set_property("config-file-path", CONFIG_INFER)
    pgie.set_property("batch-size", N)

    # 4. Tracker (NvDCF)
    tracker = buat("nvtracker", "tracker")
    tracker.set_property("ll-lib-file", TRACKER_LIB)
    tracker.set_property("ll-config-file", TRACKER_CFG)
    tracker.set_property("tracker-width", 640)
    tracker.set_property("tracker-height", 384)

    # 5. Analytics (ROI Zebra + Line-Crossing Stop Line)
    analytics = buat("nvdsanalytics", "analytics")
    analytics.set_property("config-file", CONFIG_ANALYTICS)

    elemen = [pgie, tracker, analytics]

    # 6. OSD & Display / Sink
    if TAMPILKAN:
        tiler = buat("nvmultistreamtiler", "tiler")
        tiler.set_property("rows", 1)
        tiler.set_property("columns", N)
        tiler.set_property("width", 1280)
        tiler.set_property("height", 360)
        conv = buat("nvvideoconvert", "conv")
        osd = buat("nvdsosd", "osd")
        # nv3dsink untuk Jetson; jika tidak ada (PC x86 + GPU), pakai nveglglessink
        sink = (Gst.ElementFactory.make("nv3dsink", "sink")
                or Gst.ElementFactory.make("nveglglessink", "sink"))
        if not sink:
            sys.exit("[!] Gagal membuat sink tampilan (nv3dsink/nveglglessink)")
        elemen += [tiler, conv, osd]
    else:
        sink = buat("fakesink", "sink")

    sink.set_property("sync", False)
    elemen.append(sink)

    for el in elemen:
        pipeline.add(el)

    prev = mux
    for el in elemen:
        prev.link(el)
        prev = el

    # Pad probe pada output analytics
    analytics.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, probe_analytics, 0)

    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)
    GLib.timeout_add_seconds(INTERVAL_STATUS, cetak_status)

    print("==================================================================")
    print("  NVIDIA DEEPSTREAM - PELICAN CROSSING VIOLATION DETECTION")
    print("==================================================================")
    print(f"[*] Jumlah Kamera   : {N}")
    print(f"[*] Deteksi         : {', '.join(sorted(KELAS_DIPANTAU))}")
    print(f"[*] Display GUI     : {'Aktif' if TAMPILKAN else 'Mati (Mode Headless)'}")
    if plc_modbus.manual:
        print(f"[*] State PLC       : MANUAL (PLC_STATE={plc_modbus.get_state()}, tanpa PLC)")
    else:
        print(f"[*] State PLC       : Modbus TCP ({PLC_IP}:{PLC_PORT}) reg State={PLC_REG_STATE}"
              + (f", PbCounter={PLC_REG_PBCOUNTER}" if PLC_REG_PBCOUNTER >= 0 else ""))
    print(f"[*] Log pelanggaran : {LOG_DIR}/pelanggaran_YYYY-MM-DD.csv")
    print("[*] Memulai pipeline DeepStream... (run pertama membangun engine TensorRT)")

    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\n[*] Dihentikan oleh pengguna.")
    finally:
        pipeline.set_state(Gst.State.NULL)
        plc_modbus.stop()
        print("==================================================================")
        print(f"[*] Total Pelanggaran Pejalan  : {total_pelanggaran_pejalan}")
        print(f"[*] Total Pelanggaran Kendaraan: {total_pelanggaran_kendaraan}")
        print(f"[*] Total Pelanggaran Tombol   : {total_pelanggaran_tombol}")
        print("==================================================================")


if __name__ == "__main__":
    main()
