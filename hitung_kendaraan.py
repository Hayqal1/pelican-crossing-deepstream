#!/usr/bin/env python3
import os
import sys
import time
import math
from collections import defaultdict

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib
import pyds

# ==================================================
# KONFIGURASI
# ==================================================
RTSP_KAM1 = os.environ.get("RTSP_KAM1", "rtsp://admin:GANTI_PASSWORD@192.168.100.101/")
RTSP_KAM2 = os.environ.get("RTSP_KAM2", "rtsp://admin:GANTI_PASSWORD@192.168.100.102/stream1")
SUMBER = [RTSP_KAM1, RTSP_KAM2]

CONFIG_INFER = "config_infer_yolo26.txt"
CONFIG_ANALYTICS = "config_nvdsanalytics.txt"
TRACKER_LIB = "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so"
TRACKER_CFG = "/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml"

MUX_W, MUX_H = 1280, 720      # harus sama dengan config-width/height di config_nvdsanalytics.txt
OUT_W = 1280                  # lebar jendela tampilan
N = len(SUMBER)

IS_JETSON = os.path.exists("/etc/nv_tegra_release")
TAMPILKAN = bool(os.environ.get("DISPLAY"))
DEBUG = os.environ.get("DEBUG") == "1"   # jalankan dengan DEBUG=1 untuk log detail

INTERVAL_STATUS = 10          # detik
DEBUG_INTERVAL = 100          # frame
SIMPAN_ID_DETIK = 600         # ID yang sudah dihitung disimpan 10 menit lalu dibersihkan

# Harus sesuai dengan kelas yang TIDAK difilter di config_infer_yolo26.txt
KELAS = {0: "Orang", 2: "Mobil", 3: "Motor", 5: "Bus", 7: "Truk"}
ARAH = ("Naik", "Turun")      # harus sama dengan label line-crossing-<label> di config_nvdsanalytics.txt
INVALID_ID = 0xFFFFFFFFFFFFFFFF

# ==================================================
# DATA
# ==================================================
jumlah_frame = defaultdict(int)
frame_lalu = defaultdict(int)
jumlah_deteksi = defaultdict(int)
jumlah_tracking = defaultdict(int)
deteksi_kelas = {i: defaultdict(int) for i in range(N)}
total_deteksi = defaultdict(int)

hitung_kelas = {i: {nama: 0 for nama in KELAS.values()} for i in range(N)}
hitung_detail = {i: {nama: {a: 0 for a in ARAH} for nama in KELAS.values()} for i in range(N)}
sudah_dihitung = {i: {} for i in range(N)}
analytics_count = {i: {} for i in range(N)}
analytics_aktif = {i: False for i in range(N)}

waktu_status = time.monotonic()
META_OBJ = None
META_FRAME = None


# ==================================================
# FUNGSI UMUM
# ==================================================
def iter_meta(node):
    while node is not None:
        yield node.data
        try:
            node = node.next
        except StopIteration:
            break


def total_kamera(sid):
    return sum(hitung_kelas[sid].values())


def total_semua():
    return sum(total_kamera(i) for i in range(N))


def buat(factory, nama):
    el = Gst.ElementFactory.make(factory, nama)
    if el is None:
        raise RuntimeError(f"Gagal membuat elemen {factory}")
    return el


def hubungkan(a, b):
    if not a.link(b):
        raise RuntimeError(f"Gagal menghubungkan {a.get_name()} -> {b.get_name()}")


# ==================================================
# PROBE 1: HASIL DETEKSI YOLO26 (setelah nvinfer)
# ==================================================
def probe_deteksi(pad, info, data):
    buf = info.get_buffer()
    if buf is None:
        return Gst.PadProbeReturn.OK
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(buf))
    if batch_meta is None:
        return Gst.PadProbeReturn.OK

    for item in iter_meta(batch_meta.frame_meta_list):
        frame = pyds.NvDsFrameMeta.cast(item)
        sid = int(frame.pad_index)
        if sid >= N:
            continue
        jumlah_frame[sid] += 1
        jumlah_deteksi[sid] += int(frame.num_obj_meta)
        total_deteksi[sid] += int(frame.num_obj_meta)
        frame_num = int(frame.frame_num)

        for obj_item in iter_meta(frame.obj_meta_list):
            obj = pyds.NvDsObjectMeta.cast(obj_item)
            class_id = int(obj.class_id)
            if class_id not in KELAS:
                continue
            deteksi_kelas[sid][class_id] += 1
            if DEBUG and frame_num % DEBUG_INTERVAL == 0:
                print(f"[YOLO] KAM{sid + 1} Frame={frame_num} {KELAS[class_id]} "
                      f"conf={obj.confidence:.2f} y_bawah={obj.rect_params.top + obj.rect_params.height:.0f}",
                      flush=True)
    return Gst.PadProbeReturn.OK


# ==================================================
# PROBE 2: TRACKER + ANALYTICS (setelah nvdsanalytics)
# ==================================================
def probe_analytics(pad, info, data):
    buf = info.get_buffer()
    if buf is None:
        return Gst.PadProbeReturn.OK
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(buf))
    if batch_meta is None:
        return Gst.PadProbeReturn.OK

    sekarang = time.monotonic()

    for item in iter_meta(batch_meta.frame_meta_list):
        frame = pyds.NvDsFrameMeta.cast(item)
        sid = int(frame.pad_index)
        if sid >= N:
            continue
        jumlah_tracking[sid] += int(frame.num_obj_meta)

        for user_item in iter_meta(frame.frame_user_meta_list):
            user_meta = pyds.NvDsUserMeta.cast(user_item)
            if user_meta.base_meta.meta_type != META_FRAME:
                continue
            fmeta = pyds.NvDsAnalyticsFrameMeta.cast(user_meta.user_meta_data)
            analytics_aktif[sid] = True
            analytics_count[sid] = dict(fmeta.objLCCumCnt)

        for obj_item in iter_meta(frame.obj_meta_list):
            obj = pyds.NvDsObjectMeta.cast(obj_item)
            class_id = int(obj.class_id)
            if class_id not in KELAS:
                continue
            object_id = int(obj.object_id)
            if object_id == INVALID_ID:
                continue
            jenis = KELAS[class_id]

            for user_item in iter_meta(obj.obj_user_meta_list):
                user_meta = pyds.NvDsUserMeta.cast(user_item)
                if user_meta.base_meta.meta_type != META_OBJ:
                    continue
                oinfo = pyds.NvDsAnalyticsObjInfo.cast(user_meta.user_meta_data)
                for garis in oinfo.lcStatus:
                    garis = str(garis)
                    if garis not in ARAH:
                        continue
                    key = (object_id, garis)
                    if key in sudah_dihitung[sid]:
                        continue
                    sudah_dihitung[sid][key] = sekarang
                    hitung_kelas[sid][jenis] += 1
                    hitung_detail[sid][jenis][garis] += 1
                    print(f"[HITUNG] KAM{sid + 1} | ID={object_id} | {jenis} | Arah={garis} | "
                          f"Total KAM{sid + 1}={total_kamera(sid)} | Total Semua={total_semua()}",
                          flush=True)
    return Gst.PadProbeReturn.OK


# ==================================================
# STATUS
# ==================================================
def cetak_status():
    global waktu_status
    sekarang = time.monotonic()
    dt = max(sekarang - waktu_status, 1e-6)

    print("\n" + "=" * 65)
    print(f"STATUS YOLO26 + DEEPSTREAM  ({time.strftime('%H:%M:%S')})")
    print("=" * 65)

    for sid in range(N):
        frame_baru = jumlah_frame[sid] - frame_lalu[sid]
        fps = frame_baru / dt
        deteksi = jumlah_deteksi[sid]
        tracking = jumlah_tracking[sid]
        rincian = ", ".join(f"{KELAS[c]}={n}" for c, n in sorted(deteksi_kelas[sid].items())) or "-"

        print(f"\nKAMERA {sid + 1}")
        print("-" * 40)
        print(f"FPS             : {fps:.2f}")
        print(f"Deteksi YOLO    : {deteksi}  ({rincian})")
        print(f"Objek Tracking  : {tracking}")
        print(f"Analytics       : {'Aktif' if analytics_aktif[sid] else 'Tidak aktif'} {analytics_count[sid]}")
        print("Hasil hitung    :")
        for jenis in KELAS.values():
            d = hitung_detail[sid][jenis]
            print(f"  {jenis:<6}: {hitung_kelas[sid][jenis]:<5} (Naik={d['Naik']}, Turun={d['Turun']})")
        print(f"TOTAL KAM{sid + 1}     : {total_kamera(sid)}")

        if frame_baru == 0:
            print("[MASALAH] Kamera tidak mengirim frame.")
        elif deteksi == 0:
            print("[MASALAH] YOLO tidak mendeteksi objek apa pun.")
        elif tracking == 0:
            print("[MASALAH] Ada deteksi YOLO, tapi hilang setelah tracker.")
        elif not analytics_aktif[sid]:
            print("[MASALAH] Metadata nvdsanalytics tidak terbaca. Cek config_nvdsanalytics.txt.")
        elif total_kamera(sid) == 0:
            print("[INFO] Objek terdeteksi & ter-track, belum ada yang melintasi garis. Cek posisi garis.")

        frame_lalu[sid] = jumlah_frame[sid]
        jumlah_deteksi[sid] = 0
        jumlah_tracking[sid] = 0
        deteksi_kelas[sid].clear()
        lama = [k for k, t in sudah_dihitung[sid].items() if sekarang - t > SIMPAN_ID_DETIK]
        for k in lama:
            del sudah_dihitung[sid][k]

    print("\n" + "=" * 65)
    print(f"TOTAL KESELURUHAN: {total_semua()}")
    print("=" * 65 + "\n", flush=True)
    waktu_status = sekarang
    return True


# ==================================================
# SUMBER RTSP / FILE
# ==================================================
def cb_newpad(srcbin, pad, source_bin):
    caps = pad.get_current_caps() or pad.query_caps(None)
    if caps is None or caps.get_size() == 0:
        return
    if not caps.get_structure(0).get_name().startswith("video"):
        return   # abaikan audio
    features = caps.get_features(0)
    if not features or not features.contains("memory:NVMM"):
        print("[ERROR] Decoder bukan NVMM (hardware decode tidak aktif).", flush=True)
        return
    ghost_pad = source_bin.get_static_pad("src")
    if ghost_pad.get_target() is None and not ghost_pad.set_target(pad):
        print("[ERROR] Gagal memasang source pad.", flush=True)


def buat_source(index, uri):
    source_bin = Gst.Bin.new(f"source-bin-{index}")
    src = buat("nvurisrcbin", f"source-{index}")
    src.set_property("uri", uri)
    if uri.startswith("file://"):
        src.set_property("file-loop", True)       # video file diulang terus (untuk tes)
    else:
        src.set_property("rtsp-reconnect-interval", 10)
        src.set_property("latency", 300)
        src.set_property("select-rtp-protocol", 4)  # TCP
    src.connect("pad-added", cb_newpad, source_bin)
    source_bin.add(src)
    source_bin.add_pad(Gst.GhostPad.new_no_target("src", Gst.PadDirection.SRC))
    return source_bin


def bus_call(bus, message, loop):
    if message.type == Gst.MessageType.EOS:
        print("[INFO] Stream selesai.", flush=True)
        loop.quit()
    elif message.type == Gst.MessageType.WARNING:
        err, _ = message.parse_warning()
        print(f"[WARN] {err}", flush=True)
    elif message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"[ERROR] {err}", flush=True)
        if debug:
            print(debug, flush=True)
        loop.quit()
    return True


# ==================================================
# MAIN
# ==================================================
def main():
    global META_OBJ, META_FRAME

    for path in [CONFIG_INFER, CONFIG_ANALYTICS, TRACKER_LIB, TRACKER_CFG]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"File tidak ditemukan: {path}")

    Gst.init(None)
    META_OBJ = pyds.nvds_get_user_meta_type("NVIDIA.DSANALYTICSOBJ.USER_META")
    META_FRAME = pyds.nvds_get_user_meta_type("NVIDIA.DSANALYTICSFRAME.USER_META")

    pipeline = Gst.Pipeline.new("yolo26-counter")

    mux = buat("nvstreammux", "mux")
    mux.set_property("batch-size", N)
    mux.set_property("width", MUX_W)
    mux.set_property("height", MUX_H)
    mux.set_property("live-source", 1)
    mux.set_property("batched-push-timeout", 40000)
    pipeline.add(mux)

    for i, uri in enumerate(SUMBER):
        source = buat_source(i, uri)
        pipeline.add(source)
        srcpad = source.get_static_pad("src")
        req = getattr(mux, "request_pad_simple", None) or mux.get_request_pad
        sinkpad = req(f"sink_{i}")
        if srcpad.link(sinkpad) != Gst.PadLinkReturn.OK:
            raise RuntimeError(f"Gagal menghubungkan KAM{i + 1}")

    pgie = buat("nvinfer", "pgie")
    pgie.set_property("config-file-path", CONFIG_INFER)
    pgie.set_property("batch-size", N)

    tracker = buat("nvtracker", "tracker")
    tracker.set_property("ll-lib-file", TRACKER_LIB)
    tracker.set_property("ll-config-file", TRACKER_CFG)
    tracker.set_property("tracker-width", 640)
    tracker.set_property("tracker-height", 384)

    analytics = buat("nvdsanalytics", "analytics")
    analytics.set_property("config-file", CONFIG_ANALYTICS)

    elements = [pgie, tracker, analytics]

    if TAMPILKAN:
        cols = math.ceil(math.sqrt(N))
        rows = math.ceil(N / cols)
        tile_w = OUT_W // cols
        tile_h = tile_w * 9 // 16
        tiler = buat("nvmultistreamtiler", "tiler")
        tiler.set_property("rows", rows)
        tiler.set_property("columns", cols)
        tiler.set_property("width", tile_w * cols)
        tiler.set_property("height", tile_h * rows)
        conv = buat("nvvideoconvert", "conv")
        osd = buat("nvdsosd", "osd")
        sink = buat("nv3dsink" if IS_JETSON else "nveglglessink", "sink")
        elements.extend([tiler, conv, osd])
    else:
        sink = buat("fakesink", "sink")
    sink.set_property("sync", False)
    elements.append(sink)

    for el in elements:
        pipeline.add(el)
    prev = mux
    for el in elements:
        hubungkan(prev, el)
        prev = el

    pgie.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, probe_deteksi, None)
    analytics.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, probe_analytics, None)

    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)
    GLib.timeout_add_seconds(INTERVAL_STATUS, cetak_status)

    print("=" * 65)
    print("YOLO26 + DEEPSTREAM MULTI CAMERA COUNTER")
    print("=" * 65)
    print(f"Platform    : {'Jetson' if IS_JETSON else 'x86 dGPU'}")
    print(f"Kamera      : {N}")
    print(f"KAM1        : {RTSP_KAM1.split('@')[-1]}")
    print(f"KAM2        : {RTSP_KAM2.split('@')[-1]}")
    print(f"Kelas       : {', '.join(KELAS.values())}")
    print(f"Display     : {TAMPILKAN} | Debug: {DEBUG}")
    print("=" * 65, flush=True)

    try:
        if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Gagal menjalankan pipeline.")
        loop.run()
    except KeyboardInterrupt:
        print("\n[INFO] Program dihentikan.")
    finally:
        pipeline.set_state(Gst.State.NULL)
        print("\nHASIL AKHIR")
        for sid in range(N):
            print(f"\nKAMERA {sid + 1}  (total deteksi YOLO selama berjalan: {total_deteksi[sid]})")
            for jenis in KELAS.values():
                d = hitung_detail[sid][jenis]
                print(f"  {jenis:<6}: {hitung_kelas[sid][jenis]} (Naik={d['Naik']}, Turun={d['Turun']})")
            print(f"  TOTAL : {total_kamera(sid)}")
        print(f"\nTOTAL KESELURUHAN: {total_semua()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        sys.exit(1)