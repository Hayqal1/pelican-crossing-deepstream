#!/usr/bin/env bash
# Menjalankan deteksi pelanggaran Pelican Crossing (DeepStream + YOLO26n + PLC).
#   ./run.sh                 -> tampilan aktif jika ada monitor/DISPLAY
#   HEADLESS=1 ./run.sh      -> paksa tanpa tampilan (server / SSH)
#   LOG=1 ./run.sh           -> juga simpan log terminal ke logs/terminal_YYYY-mm-dd.log
#   PLC_STATE=4 ./run.sh     -> uji tanpa PLC (state tetap 4)
cd "$(dirname "$0")"

[ -f models/yolo26n.onnx ] || { echo "[!] models/yolo26n.onnx belum ada. Jalankan: bash scripts/2_export_yolo26n.sh"; exit 1; }
[ -f DeepStream-Yolo/nvdsinfer_custom_impl_Yolo/libnvdsinfer_custom_impl_Yolo.so ] || { echo "[!] Parser belum di-compile. Jalankan: bash scripts/3_build_parser.sh"; exit 1; }

[ "${HEADLESS:-0}" = "1" ] && unset DISPLAY

# Level log GStreamer (naikkan ke 3 untuk debug)
export GST_DEBUG="${GST_DEBUG:-1}"

if [ "${LOG:-0}" = "1" ]; then
    mkdir -p logs
    python3 -u pelican_deepstream.py 2>&1 | tee -a "logs/terminal_$(date +%F).log"
else
    exec python3 -u pelican_deepstream.py
fi
