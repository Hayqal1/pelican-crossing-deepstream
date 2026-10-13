#!/usr/bin/env bash
# Cek kesiapan Jetson (JetPack 7.2.1 / DeepStream 9.1) sebelum menjalankan.
#     bash scripts/cek_sistem.sh
source "$(dirname "$0")/common.sh"
ERR=0
cek() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else warn "$1  <-- BELUM"; ERR=1; fi; }

echo "== Jetson =="
echo "   Model      : $(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo '-')"
echo "   L4T        : $(l4t_version || echo '-')"
echo "   DeepStream : $(ds_version || echo '-')"
echo "   CUDA       : $(cuda_terpasang || echo '-')"
echo "   RAM / Swap : $(free -h | awk '/Mem/ {print $2}') / $(free -h | awk '/Swap/ {print $2}')"
echo "   Python     : $PY"

echo "== DeepStream =="
cek "DeepStream terpasang"            "[ -d $DS_ROOT ]"
cek "trtexec (TensorRT)"              "[ -x $TRTEXEC ]"
cek "Plugin nvurisrcbin"              "gst-inspect-1.0 nvurisrcbin"
cek "Plugin nvinfer"                  "gst-inspect-1.0 nvinfer"
cek "Plugin nvtracker"                "gst-inspect-1.0 nvtracker"
cek "Plugin nvdsanalytics"            "gst-inspect-1.0 nvdsanalytics"
cek "Plugin nv3dsink"                 "gst-inspect-1.0 nv3dsink"
cek "Config tracker NvDCF_perf"       "[ -f $DS_ROOT/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml ]"

echo "== Python ($VENV) =="
cek "Python GStreamer (gi)"           "$PY -c 'import gi; gi.require_version(\"Gst\",\"1.0\"); from gi.repository import Gst'"
cek "pyds"                            "$PY -c 'import pyds'"
cek "numpy 1.x"                       "$PY -c 'import numpy,sys; sys.exit(int(numpy.__version__.split(\".\")[0])>=2)'"
cek "pymodbus (PLC)"                  "$PY -c 'import pymodbus'"

echo "== Model =="
cek "models/yolo26n.onnx"             "[ -f $PROJ_DIR/models/yolo26n.onnx ]"
cek "models/labels.txt"               "[ -f $PROJ_DIR/models/labels.txt ]"
cek "Library parser YOLO"             "[ -f $PROJ_DIR/DeepStream-Yolo/nvdsinfer_custom_impl_Yolo/libnvdsinfer_custom_impl_Yolo.so ]"
cek "yolo26.engine"                   "[ -s $PROJ_DIR/yolo26.engine ]"

echo
[ $ERR -eq 0 ] && ok "Semua siap. Jalankan: HEADLESS=1 ./run.sh" || warn "Ada yang belum siap. Jalankan: bash setup_jetson.sh"
exit $ERR
