#!/usr/bin/env bash
# Cek kesiapan sistem sebelum menjalankan.
#     bash scripts/cek_sistem.sh
source "$(dirname "$0")/common.sh"
ERR=0
cek() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else warn "$1  <-- BELUM"; ERR=1; fi; }

echo "== Sistem =="
echo "   Arsitektur : $ARCH"
echo "   DeepStream : $(ds_version || echo '-')"
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null | sed 's/^/   GPU        : /'
[ -f /etc/nv_tegra_release ] && echo "   L4T        : $(head -n1 /etc/nv_tegra_release)"

echo "== DeepStream & Python =="
cek "DeepStream terpasang"            "[ -d $DS_ROOT ]"
cek "Plugin nvurisrcbin"              "gst-inspect-1.0 nvurisrcbin"
cek "Plugin nvinfer"                  "gst-inspect-1.0 nvinfer"
cek "Plugin nvtracker"                "gst-inspect-1.0 nvtracker"
cek "Plugin nvdsanalytics"            "gst-inspect-1.0 nvdsanalytics"
cek "Python GStreamer (gi)"           "python3 -c 'import gi; gi.require_version(\"Gst\",\"1.0\"); from gi.repository import Gst'"
cek "pyds"                            "python3 -c 'import pyds'"
cek "pymodbus (PLC)"                  "python3 -c 'import pymodbus'"
cek "Config tracker NvDCF_perf"       "[ -f $DS_ROOT/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml ]"

echo "== Model =="
cek "models/yolo26n.onnx"             "[ -f $PROJ_DIR/models/yolo26n.onnx ]"
cek "models/labels.txt"               "[ -f $PROJ_DIR/models/labels.txt ]"
cek "Library parser YOLO"             "[ -f $PROJ_DIR/DeepStream-Yolo/nvdsinfer_custom_impl_Yolo/libnvdsinfer_custom_impl_Yolo.so ]"
if ls "$PROJ_DIR"/*.engine >/dev/null 2>&1; then ok "Engine TensorRT sudah ada (run cepat)"; else warn "Engine belum ada (dibangun saat run pertama, bisa >10 menit)"; fi

echo
[ $ERR -eq 0 ] && ok "Semua siap. Jalankan: ./run.sh" || warn "Ada yang belum siap, lihat README."
exit $ERR
