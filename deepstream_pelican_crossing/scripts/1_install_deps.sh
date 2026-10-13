#!/usr/bin/env bash
# LANGKAH 1 — Pasang dependensi sistem + Python bindings DeepStream (pyds).
# Jalankan di mesin DeepStream (Jetson / PC dengan GPU NVIDIA):
#     bash scripts/1_install_deps.sh
set -e
source "$(dirname "$0")/common.sh"

DSV="$(ds_version)"
[ -n "$DSV" ] || gagal "DeepStream tidak ditemukan di $DS_ROOT. Pasang DeepStream SDK dulu (lihat README bagian 2)."
ok "DeepStream $DSV terdeteksi ($ARCH)"

info "Memasang paket sistem (butuh sudo)..."
sudo apt-get update
sudo apt-get install -y \
    git wget curl build-essential \
    python3-pip python3-venv python3-dev \
    python3-gi python3-gst-1.0 gir1.2-gst-rtsp-server-1.0 \
    libgirepository1.0-dev libcairo2-dev \
    gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly gstreamer1.0-libav

# Skrip tambahan resmi DeepStream (codec/plugin tambahan untuk RTSP)
if [ -x "$DS_ROOT/user_additional_install.sh" ]; then
    info "Menjalankan user_additional_install.sh bawaan DeepStream..."
    sudo "$DS_ROOT/user_additional_install.sh" || warn "user_additional_install.sh gagal, lanjut."
fi

# ---------------------------------------------------------------- pymodbus (PLC)
info "Memasang pymodbus (komunikasi PLC Modbus TCP)..."
pip3 install -q pymodbus 2>/dev/null || pip3 install -q --break-system-packages pymodbus \
    || warn "Gagal memasang pymodbus. Coba manual: pip3 install pymodbus"
python3 -c "import pymodbus" 2>/dev/null && ok "pymodbus terpasang"

# ---------------------------------------------------------------- pyds
if python3 -c "import pyds" 2>/dev/null; then
    ok "pyds sudah terpasang"
    exit 0
fi

# Pemetaan versi DeepStream -> rilis pyds (deepstream_python_apps).
# Bisa dipaksa: PYDS_TAG=v1.2.0 bash scripts/1_install_deps.sh
case "$DSV" in
    7.1) TAG_DEF=v1.2.0 ;;
    7.0) TAG_DEF=v1.1.11 ;;
    6.4) TAG_DEF=v1.1.10 ;;
    6.3) TAG_DEF=v1.1.8 ;;
    *)   TAG_DEF=latest ;;
esac
TAG="${PYDS_TAG:-$TAG_DEF}"
PYV="cp$(python3 -c 'import sys;print(f"{sys.version_info[0]}{sys.version_info[1]}")')"
case "$ARCH" in aarch64) WARCH=linux_aarch64 ;; *) WARCH=linux_x86_64 ;; esac

if [ "$TAG" = "latest" ]; then
    API="https://api.github.com/repos/NVIDIA-AI-IOT/deepstream_python_apps/releases/latest"
else
    API="https://api.github.com/repos/NVIDIA-AI-IOT/deepstream_python_apps/releases/tags/$TAG"
fi
info "Mencari wheel pyds ($TAG, $PYV, $WARCH)..."
URL="$(curl -fsSL "$API" | grep -oE '"browser_download_url": *"[^"]+\.whl"' \
       | grep -oE 'https://[^"]+' | grep "$PYV" | grep "$WARCH" | head -n1 || true)"

if [ -z "$URL" ]; then
    warn "Wheel pyds yang cocok tidak ditemukan otomatis."
    warn "Unduh manual dari https://github.com/NVIDIA-AI-IOT/deepstream_python_apps/releases"
    warn "(pilih rilis yang sesuai DeepStream $DSV, file pyds-*-$PYV-*-$WARCH.whl), lalu:"
    warn "    pip3 install ./pyds-*.whl"
    exit 1
fi

TMP="$(mktemp -d)"
wget -q --show-progress -P "$TMP" "$URL"
pip3 install "$TMP"/*.whl || pip3 install --break-system-packages "$TMP"/*.whl
# pyds tidak mendukung numpy 2.x
pip3 install "numpy<2" 2>/dev/null || pip3 install --break-system-packages "numpy<2" || true
rm -rf "$TMP"

python3 -c "import pyds" && ok "pyds terpasang" || gagal "pyds gagal diimpor"
