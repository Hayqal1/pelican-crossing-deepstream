#!/usr/bin/env bash
# Menjalankan deteksi pelanggaran Pelican Crossing di Jetson Orin Nano.
#   HEADLESS=1 ./run.sh      -> tanpa tampilan (disarankan, hemat RAM)
#   ./run.sh                 -> dengan tampilan (butuh monitor & desktop aktif)
#   LOG=1 ./run.sh           -> juga simpan output terminal ke logs/terminal_YYYY-mm-dd.log
#   PLC_STATE=4 ./run.sh     -> uji tanpa PLC (state tetap 4)
cd "$(dirname "$0")" || exit 1
source scripts/common.sh

[ -f DeepStream-Yolo/nvdsinfer_custom_impl_Yolo/libnvdsinfer_custom_impl_Yolo.so ] || {
    echo "[!] Parser belum di-compile. Jalankan: bash setup_jetson.sh parser"; exit 1; }
[ -s yolo26.engine ] || {
    echo "[!] yolo26.engine belum ada. Jalankan: bash setup_jetson.sh engine"; exit 1; }
"$PY" -c "import pyds" 2>/dev/null || {
    echo "[!] pyds tidak ditemukan di $PY. Jalankan: bash setup_jetson.sh pyds"; exit 1; }

[ "${HEADLESS:-0}" = "1" ] && unset DISPLAY

# Kunci clock maksimum bila sudo tanpa password tersedia (service systemd sudah melakukannya)
sudo -n /usr/bin/jetson_clocks >/dev/null 2>&1 && echo "[*] jetson_clocks aktif"

export GST_DEBUG="${GST_DEBUG:-1}"
# DeepStream 9.1: kurangi penurunan performa NvDCF (rekomendasi release notes)
export NVDS_DISABLE_CUDADEV_BLOCKINGSYNC="${NVDS_DISABLE_CUDADEV_BLOCKINGSYNC:-1}"

if [ "${LOG:-0}" = "1" ]; then
    mkdir -p logs
    "$PY" -u pelican_deepstream.py 2>&1 | tee -a "logs/terminal_$(date +%F).log"
else
    exec "$PY" -u pelican_deepstream.py
fi
