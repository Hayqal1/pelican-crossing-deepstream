#!/usr/bin/env bash
# Fungsi bersama untuk skrip-skrip di folder ini.

PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DS_ROOT="/opt/nvidia/deepstream/deepstream"
ARCH="$(uname -m)"   # x86_64 (PC + GPU NVIDIA) atau aarch64 (Jetson)

info()  { echo -e "\e[1;34m[*]\e[0m $*"; }
ok()    { echo -e "\e[1;32m[OK]\e[0m $*"; }
warn()  { echo -e "\e[1;33m[!]\e[0m $*"; }
gagal() { echo -e "\e[1;31m[X]\e[0m $*"; exit 1; }

# Versi DeepStream, mis. "7.1"
ds_version() {
    if [ -f "$DS_ROOT/version" ]; then
        grep -oE '[0-9]+\.[0-9]+' "$DS_ROOT/version" | head -n1
    fi
}

# CUDA_VER yang dipakai untuk compile parser DeepStream-Yolo
# (sumber: tabel di DeepStream-Yolo/docs/YOLO26.md)
cuda_ver_for_ds() {
    local ds="$1"
    if [ "$ARCH" = "aarch64" ]; then
        case "$ds" in
            8.0) echo 13.0 ;;
            7.1) echo 12.6 ;;
            7.0|6.4) echo 12.2 ;;
            6.3|6.2|6.1) echo 11.4 ;;
            6.0|5.1) echo 10.2 ;;
        esac
    else
        case "$ds" in
            8.0) echo 12.8 ;;
            7.1) echo 12.6 ;;
            7.0|6.4) echo 12.2 ;;
            6.3) echo 12.1 ;;
            6.2) echo 11.8 ;;
            6.1) echo 11.6 ;;
            6.0) echo 11.4 ;;
            5.1) echo 11.1 ;;
        esac
    fi
}
