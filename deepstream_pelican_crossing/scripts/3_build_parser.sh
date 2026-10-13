#!/usr/bin/env bash
# LANGKAH 3 — Compile library parser YOLO (DeepStream-Yolo) untuk nvinfer.
# Wajib dijalankan di mesin DeepStream.
#     bash scripts/3_build_parser.sh
# Paksa versi CUDA bila deteksi otomatis salah:
#     CUDA_VER=12.6 bash scripts/3_build_parser.sh
set -e
source "$(dirname "$0")/common.sh"

DSY="$PROJ_DIR/DeepStream-Yolo"
DSV="$(ds_version)"
[ -n "$DSV" ] || gagal "DeepStream tidak ditemukan di $DS_ROOT"

if [ -z "$CUDA_VER" ]; then
    CUDA_VER="$(cuda_ver_for_ds "$DSV")"
    [ -n "$CUDA_VER" ] || gagal "Versi DeepStream $DSV belum dipetakan. Jalankan dengan CUDA_VER=xx.y"
fi
export CUDA_VER
[ -d "/usr/local/cuda-$CUDA_VER" ] || warn "/usr/local/cuda-$CUDA_VER tidak ada. Cek: ls /usr/local | grep cuda"
info "DeepStream $DSV | $ARCH | CUDA_VER=$CUDA_VER"

if [ ! -d "$DSY" ]; then
    info "Clone DeepStream-Yolo..."
    git clone --depth 1 https://github.com/marcoslucianops/DeepStream-Yolo "$DSY"
fi

make -C "$DSY/nvdsinfer_custom_impl_Yolo" clean
make -C "$DSY/nvdsinfer_custom_impl_Yolo" -j"$(nproc)"

LIB="$DSY/nvdsinfer_custom_impl_Yolo/libnvdsinfer_custom_impl_Yolo.so"
[ -f "$LIB" ] && ok "Library siap: $LIB" || gagal "Compile gagal"
