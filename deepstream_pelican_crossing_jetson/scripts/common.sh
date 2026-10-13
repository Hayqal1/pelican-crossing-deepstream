#!/usr/bin/env bash
# Fungsi & variabel bersama — Jetson Orin Nano (JetPack 7.2.1 / DeepStream 9.1)

PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DS_ROOT="/opt/nvidia/deepstream/deepstream"
ARCH="$(uname -m)"
TRTEXEC="/usr/src/tensorrt/bin/trtexec"
VENV="${DS_VENV:-$HOME/ds-venv}"            # virtualenv berisi pyds, numpy, pymodbus
if [ -x "$VENV/bin/python3" ]; then PY="$VENV/bin/python3"; else PY="python3"; fi

info()  { echo -e "\e[1;34m[*]\e[0m $*"; }
ok()    { echo -e "\e[1;32m[OK]\e[0m $*"; }
warn()  { echo -e "\e[1;33m[!]\e[0m $*"; }
gagal() { echo -e "\e[1;31m[X]\e[0m $*"; exit 1; }
judul() { echo; echo -e "\e[1;36m==================== $* ====================\e[0m"; }

is_jetson() { [ -f /etc/nv_tegra_release ]; }

# Versi L4T, mis. "39.2.1"
l4t_version() {
    [ -f /etc/nv_tegra_release ] || return
    local r rev
    r="$(grep -oE 'R[0-9]+' /etc/nv_tegra_release | head -n1 | tr -d R)"
    rev="$(grep -oE 'REVISION: [0-9.]+' /etc/nv_tegra_release | grep -oE '[0-9.]+$')"
    echo "$r.$rev"
}

ds_version() {
    [ -f "$DS_ROOT/version" ] && grep -oE '[0-9]+\.[0-9]+' "$DS_ROOT/version" | head -n1
}

# Versi CUDA terpasang (mis. 13.2) — dari folder /usr/local/cuda-X.Y
cuda_terpasang() {
    ls -d /usr/local/cuda-[0-9]* 2>/dev/null | sed 's|.*/cuda-||' | sort -V | tail -n1
}

ram_mb() { awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo; }
