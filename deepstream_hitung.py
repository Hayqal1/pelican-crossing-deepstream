#!/usr/bin/env python3
import os
import sys
import time
import datetime

import gi
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst
import pyds

# =====================================================
# KONFIGURASI
# =====================================================
SUMBER = [
    os.environ.get("RTSP_KAM1", "rtsp://admin:GANTI_PASSWORD@192.168.100.101/"),
    os.environ.get("RTSP_KAM2", "rtsp://admin:GANTI_PASSWORD@192.168.100.102/stream2"),  # ganti ke kamera ke-2
]
MUX_W, MUX_H = 1280, 720   # harus sama dengan config-width/height di config_nvdsanalytics.txt
CONFIG_INFER = "config_infer_yolo26.txt"
CONFIG_ANALYTICS = "config_nvdsanalytics.txt"
TRACKER_LIB = "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so"
TRACKER_CFG = "/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml"
TAMPILKAN = bool(os.environ.get("DISPLAY"))   # otomatis mati saat headless/SSH
INTERVAL_STATUS = 60                          # detik
# =====================================================

N = len(SUMBER)
hitung = {i: {} for i in range(N)}
jumlah_frame = {i: 0 for i in range(N)}
frame_lalu = {i: 0 for i in range(N)}
waktu_lalu = time.time()

META_OBJ = None
META_FRAME = None


def total_semua():
    return sum(sum(h.values()) for h in hitung.values())


def iter_list(l):
    while l is not None:
        yield l.data
        try:
            l = l.next
        except StopIteration:
            break


def probe_analytics(pad, info, u_data):
    buf = info.get_buffer()
    if not buf:
        return Gst.PadProbeReturn.OK

    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(buf))
    for data in iter_list(batch_meta.frame_meta_list):
        frame_meta = pyds.NvDsFrameMeta.cast(data)
        sid = frame_meta.pad_index
        jumlah_frame[sid] += 1

        for udata in iter_list(frame_meta.frame_user_meta_list):
            user_meta = pyds.NvDsUserMeta.cast(udata)
            if user_meta.base_meta.meta_type == META_FRAME:
                fmeta = pyds.NvDsAnalyticsFrameMeta.cast(user_meta.user_meta_data)
                hitung[sid] = dict(fmeta.objLCCumCnt)

        for odata in iter_list(frame_meta.obj_meta_list):
            obj_meta = pyds.NvDsObjectMeta.cast(odata)
            for udata in iter_list(obj_meta.obj_user_meta_list):
                user_meta = pyds.NvDsUserMeta.cast(udata)
                if user_meta.base_meta.meta_type != META_OBJ:
                    continue
                oinfo = pyds.NvDsAnalyticsObjInfo.cast(user_meta.user_meta_data)
                if oinfo.lcStatus:
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    arah = ",".join(oinfo.lcStatus)
                    print(f"[{now}] [KAM{sid + 1}] #{obj_meta.object_id} ({obj_meta.obj_label}) "
                          f"melintas {arah} | KAM{sid + 1}: {sum(hitung[sid].values())} | "
                          f"Total: {total_semua()}", flush=True)

    return Gst.PadProbeReturn.OK


def cetak_status():
    global waktu_lalu
    sekarang = time.time()
    dt = max(1e-6, sekarang - waktu_lalu)
    bagian = []#!/usr/bin/env python3
import os
import sys
import time
import datetime

import gi
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst
import pyds

# =====================================================
# KONFIGURASI
# =====================================================
SUMBER = [
    os.environ.get("RTSP_KAM1", "rtsp://admin:GANTI_PASSWORD@192.168.100.101/"),
    os.environ.get("RTSP_KAM2", "rtsp://admin:GANTI_PASSWORD@192.168.100.102/stream2"),  # ganti ke kamera ke-2
]
MUX_W, MUX_H = 1280, 720   # harus sama dengan config-width/height di config_nvdsanalytics.txt
CONFIG_INFER = "config_infer_yolo26.txt"
CONFIG_ANALYTICS = "config_nvdsanalytics.txt"
TRACKER_LIB = "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so"
TRACKER_CFG = "/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml"
TAMPILKAN = bool(os.environ.get("DISPLAY"))   # otomatis mati saat headless/SSH
INTERVAL_STATUS = 60                          # detik
# =====================================================

N = len(SUMBER)
hitung = {i: {} for i in range(N)}
jumlah_frame = {i: 0 for i in range(N)}
frame_lalu = {i: 0 for i in range(N)}
waktu_lalu = time.time()

META_OBJ = None
META_FRAME = None


def total_semua():
    return sum(sum(h.values()) for h in hitung.values())


def iter_list(l):
    while l is not None:
        yield l.data
        try:
            l = l.next
        except StopIteration:
            break


def probe_analytics(pad, info, u_data):
    buf = info.get_buffer()
    if not buf:
        return Gst.PadProbeReturn.OK

    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(buf))
    for data in iter_list(batch_meta.frame_meta_list):
        frame_meta = pyds.NvDsFrameMeta.cast(data)
        sid = frame_meta.pad_index
        jumlah_frame[sid] += 1

        for udata in iter_list(frame_meta.frame_user_meta_list):
            user_meta = pyds.NvDsUserMeta.cast(udata)
            if user_meta.base_meta.meta_type == META_FRAME:
                fmeta = pyds.NvDsAnalyticsFrameMeta.cast(user_meta.user_meta_data)
                hitung[sid] = dict(fmeta.objLCCumCnt)

        for odata in iter_list(frame_meta.obj_meta_list):
            obj_meta = pyds.NvDsObjectMeta.cast(odata)
            for udata in iter_list(obj_meta.obj_user_meta_list):
                user_meta = pyds.NvDsUserMeta.cast(udata)
                if user_meta.base_meta.meta_type != META_OBJ:
                    continue
                oinfo = pyds.NvDsAnalyticsObjInfo.cast(user_meta.user_meta_data)
                if oinfo.lcStatus:
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    arah = ",".join(oinfo.lcStatus)
                    print(f"[{now}] [KAM{sid + 1}] #{obj_meta.object_id} ({obj_meta.obj_label}) "
                          f"melintas {arah} | KAM{sid + 1}: {sum(hitung[sid].values())} | "
                          f"Total: {total_semua()}", flush=True)

    return Gst.PadProbeReturn.OK


def cetak_status():
    global waktu_lalu
    sekarang = time.time()
    dt = max(1e-6, sekarang - waktu_lalu)
    bagian = []
    for i in range(N):
        fps = (jumlah_frame[i] - frame_lalu[i]) / dt
        frame_lalu[i] = jumlah_frame[i]
        bagian.append(f"KAM{i + 1}: {sum(hitung[i].values())} {hitung[i]} ({fps:.1f} FPS)")
    waktu_lalu = sekarang
    print(f"[STATUS] {' | '.join(bagian)} | Total: {total_semua()}", flush=True)
    return True


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
        sys.exit("[!] nvurisrcbin tidak ditemukan. Pastikan DeepStream terpasang.")
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


def main():
    global META_OBJ, META_FRAME
    Gst.init(None)
    META_OBJ = pyds.nvds_get_user_meta_type("NVIDIA.DSANALYTICSOBJ.USER_META")
    META_FRAME = pyds.nvds_get_user_meta_type("NVIDIA.DSANALYTICSFRAME.USER_META")

    pipeline = Gst.Pipeline()

    mux = buat("nvstreammux", "mux")
    mux.set_property("batch-size", N)
    mux.set_property("width", MUX_W)
    mux.set_property("height", MUX_H)
    mux.set_property("batched-push-timeout", 40000)
    mux.set_property("live-source", 1)
    pipeline.add(mux)

    for i, uri in enumerate(SUMBER):
        sb = buat_source_bin(i, uri)
        pipeline.add(sb)
        sb.get_static_pad("src").link(minta_pad(mux, f"sink_{i}"))

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

    elemen = [pgie, tracker, analytics]

    if TAMPILKAN:
        tiler = buat("nvmultistreamtiler", "tiler")
        tiler.set_property("rows", 1)
        tiler.set_property("columns", N)
        tiler.set_property("width", 1280)
        tiler.set_property("height", 360)
        conv = buat("nvvideoconvert", "conv")
        osd = buat("nvdsosd", "osd")
        sink = buat("nv3dsink", "sink")
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

    analytics.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, probe_analytics, 0)

    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)
    GLib.timeout_add_seconds(INTERVAL_STATUS, cetak_status)

    print(f"[*] Tampilan: {'Aktif' if TAMPILKAN else 'Mati (headless)'}")
    print("[*] Memulai pipeline... (run pertama membangun engine TensorRT, bisa >10 menit)")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\n[*] Dihentikan oleh pengguna.")
    finally:
        pipeline.set_state(Gst.State.NULL)
        for i in range(N):
            print(f"[*] KAM{i + 1}: {sum(hitung[i].values())} {hitung[i]}")
        print(f"[*] Selesai. Total: {total_semua()}")


if __name__ == "__main__":
    main()



# gst-launch-1.0 -e rtspsrc location="rtsp://admin:GANTI_PASSWORD@192.168.100.102/stream1" protocols=tcp ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink
# gst-launch-1.0 -e rtspsrc location="rtsp://admin:GANTI_PASSWORD@192.168.100.101" protocols=tcp ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink

    for i in range(N):
        fps = (jumlah_frame[i] - frame_lalu[i]) / dt
        frame_lalu[i] = jumlah_frame[i]
        bagian.append(f"KAM{i + 1}: {sum(hitung[i].values())} {hitung[i]} ({fps:.1f} FPS)")
    waktu_lalu = sekarang
    print(f"[STATUS] {' | '.join(bagian)} | Total: {total_semua()}", flush=True)
    return True


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
        sys.exit("[!] nvurisrcbin tidak ditemukan. Pastikan DeepStream terpasang.")
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


def main():
    global META_OBJ, META_FRAME
    Gst.init(None)
    META_OBJ = pyds.nvds_get_user_meta_type("NVIDIA.DSANALYTICSOBJ.USER_META")
    META_FRAME = pyds.nvds_get_user_meta_type("NVIDIA.DSANALYTICSFRAME.USER_META")

    pipeline = Gst.Pipeline()

    mux = buat("nvstreammux", "mux")
    mux.set_property("batch-size", N)
    mux.set_property("width", MUX_W)
    mux.set_property("height", MUX_H)
    mux.set_property("batched-push-timeout", 40000)
    mux.set_property("live-source", 1)
    pipeline.add(mux)

    for i, uri in enumerate(SUMBER):
        sb = buat_source_bin(i, uri)
        pipeline.add(sb)
        sb.get_static_pad("src").link(minta_pad(mux, f"sink_{i}"))

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

    elemen = [pgie, tracker, analytics]

    if TAMPILKAN:
        tiler = buat("nvmultistreamtiler", "tiler")
        tiler.set_property("rows", 1)
        tiler.set_property("columns", N)
        tiler.set_property("width", 1280)
        tiler.set_property("height", 360)
        conv = buat("nvvideoconvert", "conv")
        osd = buat("nvdsosd", "osd")
        sink = buat("nv3dsink", "sink")
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

    analytics.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, probe_analytics, 0)

    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)
    GLib.timeout_add_seconds(INTERVAL_STATUS, cetak_status)

    print(f"[*] Tampilan: {'Aktif' if TAMPILKAN else 'Mati (headless)'}")
    print("[*] Memulai pipeline... (run pertama membangun engine TensorRT, bisa >10 menit)")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\n[*] Dihentikan oleh pengguna.")
    finally:
        pipeline.set_state(Gst.State.NULL)
        for i in range(N):
            print(f"[*] KAM{i + 1}: {sum(hitung[i].values())} {hitung[i]}")
        print(f"[*] Selesai. Total: {total_semua()}")


if __name__ == "__main__":
    main()



# gst-launch-1.0 -e rtspsrc location="rtsp://admin:GANTI_PASSWORD@192.168.100.102/stream1" protocols=tcp ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink
# gst-launch-1.0 -e rtspsrc location="rtsp://admin:GANTI_PASSWORD@192.168.100.101" protocols=tcp ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink
