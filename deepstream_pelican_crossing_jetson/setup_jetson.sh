#!/usr/bin/env bash
################################################################################
# INSTALLER — Pelican Crossing (DeepStream + YOLO26n + PLC)
# Target : Jetson Orin Nano 4GB | JetPack 7.2.1 (L4T 39.2.1) | Ubuntu 24.04
#          DeepStream 9.1 | CUDA 13.2 | TensorRT 10.16 | Python 3.12
#
# Pemakaian:
#   bash setup_jetson.sh                 -> jalankan semua tahap berurutan
#   bash setup_jetson.sh <tahap>         -> jalankan satu tahap saja
#   bash setup_jetson.sh --dari <tahap>  -> lanjut mulai tahap tertentu
#   TANPA_GUI=1 bash setup_jetson.sh     -> sekalian matikan desktop (hemat RAM)
#
# Tahap: cek optimasi deepstream pyds parser engine verifikasi
#
# Setiap tahap aman diulang (yang sudah selesai akan dilewati).
# Jika ada tahap gagal, perbaiki lalu jalankan: bash setup_jetson.sh --dari <tahap>
################################################################################
set -eo pipefail
cd "$(dirname "$0")"
source scripts/common.sh

TAHAP_SEMUA=(cek optimasi deepstream pyds parser engine verifikasi)
DS_DEB_NAMA="deepstream-9.1_9.1.0-1_arm64.deb"
SRC_DIR="$HOME/ds-src"                         # folder build pyds
LOG="$PROJ_DIR/setup_jetson.log"

# ------------------------------------------------------------------ 1. cek
tahap_cek() {
    judul "1/7 CEK PERANGKAT"
    is_jetson || gagal "Bukan Jetson (/etc/nv_tegra_release tidak ada)."
    local model l4t
    model="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo '?')"
    l4t="$(l4t_version)"
    info "Perangkat : $model"
    info "L4T       : $l4t   (JetPack 7.2.1 = 39.2.1)"
    info "Ubuntu    : $(. /etc/os-release; echo "$VERSION_ID")"
    info "RAM       : $(ram_mb) MB"
    info "CUDA      : $(cuda_terpasang || echo '-')"
    [ "${l4t%%.*}" = "39" ] || warn "Installer ini disiapkan untuk JetPack 7.2.x (L4T 39). Versi Anda: $l4t"
    [ -x "$TRTEXEC" ] || {
        info "TensorRT (trtexec) belum ada, memasang komponen JetPack..."
        sudo apt-get update && sudo apt-get install -y nvidia-jetpack || true
    }
    [ -x "$TRTEXEC" ] && ok "trtexec ada" || warn "trtexec belum ada — pasang JetPack lengkap via SDK Manager"
    local free_gb; free_gb="$(df -BG --output=avail "$HOME" | tail -n1 | tr -dc 0-9)"
    [ "${free_gb:-0}" -ge 15 ] || warn "Ruang disk tersisa ${free_gb}GB; disarankan >= 15GB (DeepStream + build)."
    ok "Cek selesai"
}

# ------------------------------------------------------------------ 2. optimasi
tahap_optimasi() {
    judul "2/7 OPTIMASI ORIN NANO 4GB"
    # Mode daya maksimal (MAXN / MAXN_SUPER)
    if command -v nvpmodel >/dev/null; then
        local id cur
        id="$(grep -oE 'POWER_MODEL ID=[0-9]+ NAME=MAXN[A-Z_]*' /etc/nvpmodel.conf 2>/dev/null \
              | tail -n1 | grep -oE 'ID=[0-9]+' | cut -d= -f2)"
        cur="$(sudo nvpmodel -q 2>/dev/null | tail -n1 | tr -dc 0-9)"
        if [ -n "$id" ] && [ "$cur" != "$id" ]; then
            info "Mode daya -> ID $id (MAXN)"
            echo no | sudo nvpmodel -m "$id" || true
            warn "Jika nvpmodel meminta reboot, reboot setelah setup selesai."
        else
            ok "Mode daya: $(sudo nvpmodel -q 2>/dev/null | head -n1)"
        fi
    fi
    # Swap 6GB (build pyds & engine butuh memori besar)
    if ! swapon --show=NAME --noheadings | grep -q '^/swapfile$'; then
        info "Membuat swap file 6GB..."
        sudo fallocate -l 6G /swapfile
        sudo chmod 600 /swapfile
        sudo mkswap /swapfile >/dev/null
        sudo swapon /swapfile
        grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
        ok "Swap aktif"
    else
        ok "Swap /swapfile sudah aktif"
    fi
    if [ "${TANPA_GUI:-0}" = "1" ]; then
        sudo systemctl set-default multi-user.target
        warn "Desktop dimatikan mulai boot berikutnya. Kembalikan: sudo systemctl set-default graphical.target"
    fi
    free -h | sed -n 1,3p
}

# ------------------------------------------------------------------ 3. deepstream
tahap_deepstream() {
    judul "3/7 DEEPSTREAM 9.1"
    info "Memasang prasyarat DeepStream..."
    sudo apt-get update
    sudo apt-get install -y \
        libssl3 libssl-dev libcurl4-openssl-dev \
        libgstreamer1.0-0 gstreamer1.0-tools \
        gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
        gstreamer1.0-libav libgstreamer-plugins-base1.0-dev libgstrtspserver-1.0-0 \
        libjansson4 libyaml-cpp-dev libmosquitto1 \
        git wget curl build-essential pkg-config

    if [ "$(ds_version)" = "9.1" ]; then
        ok "DeepStream 9.1 sudah terpasang"
    else
        local deb=""
        for d in "$PROJ_DIR" "$HOME/Downloads" "$HOME"; do
            [ -f "$d/$DS_DEB_NAMA" ] && deb="$d/$DS_DEB_NAMA" && break
        done
        [ -n "$deb" ] || gagal "File $DS_DEB_NAMA tidak ditemukan.
    Unduh dari halaman DeepStream SDK NVIDIA (versi Jetson / arm64), taruh di
    $PROJ_DIR atau ~/Downloads, lalu jalankan: bash setup_jetson.sh --dari deepstream"
        info "Memasang $deb ..."
        sudo apt-get install -y "$deb"
        sudo ldconfig
    fi
    rm -rf ~/.cache/gstreamer-1.0
    deepstream-app --version-all 2>/dev/null | head -n 8 || true
    gst-inspect-1.0 nvinfer >/dev/null 2>&1 && ok "Plugin DeepStream terdeteksi" \
        || gagal "Plugin nvinfer tidak terdeteksi. Cek instalasi DeepStream."
}

# ------------------------------------------------------------------ 4. pyds
tahap_pyds() {
    judul "4/7 PYTHON: pyds + numpy + pymodbus (virtualenv $VENV)"
    sudo apt-get install -y \
        python3-gi python3-dev python3-gst-1.0 python-gi-dev git meson ninja-build \
        python3 python3-pip python3-venv cmake g++ build-essential libglib2.0-dev \
        libglib2.0-dev-bin libgstreamer1.0-dev libtool m4 autoconf automake \
        libgirepository-2.0-dev libcairo2-dev

    # venv memakai paket sistem juga (python3-gi / GStreamer)
    if [ ! -x "$VENV/bin/python3" ]; then
        python3 -m venv --system-site-packages "$VENV"
    fi
    PY="$VENV/bin/python3"
    "$PY" -m pip install -q --upgrade pip
    "$PY" -m pip install -q build "numpy==1.26.4" pymodbus
    ok "numpy $("$PY" -c 'import numpy;print(numpy.__version__)') | pymodbus $("$PY" -c 'import pymodbus;print(pymodbus.__version__)')"

    if "$PY" -c "import pyds" 2>/dev/null; then
        ok "pyds sudah terpasang di venv"
        return
    fi

    mkdir -p "$SRC_DIR"
    local dpa="$SRC_DIR/deepstream_python_apps"
    if [ ! -d "$dpa" ]; then
        info "Clone deepstream_python_apps..."
        git clone https://github.com/NVIDIA-AI-IOT/deepstream_python_apps "$dpa"
    fi
    cd "$dpa"
    git submodule update --init
    python3 bindings/3rdparty/git-partial-submodule/git-partial-submodule.py restore-sparse

    info "Build gst-python..."
    cd bindings/3rdparty/gstreamer/subprojects/gst-python/
    [ -d build ] || meson setup build
    cd build
    ninja
    sudo ninja install

    info "Build pyds (10–30 menit di Orin Nano, memakai 2 core agar RAM cukup)..."
    cd "$dpa/bindings"
    rm -rf dist build
    export CMAKE_ARGS="-DDS_PATH=$DS_ROOT/"
    export CMAKE_BUILD_PARALLEL_LEVEL="${JOBS:-2}"
    "$PY" -m build
    "$PY" -m pip install --force-reinstall dist/pyds-*.whl
    "$PY" -m pip install -q "numpy==1.26.4"       # pastikan numpy 1.x tetap
    cd "$PROJ_DIR"
    "$PY" -c "import pyds" && ok "pyds terpasang" || gagal "pyds gagal diimpor"
}

# ------------------------------------------------------------------ 5. parser
tahap_parser() {
    judul "5/7 PARSER YOLO (DeepStream-Yolo)"
    local cuda="${CUDA_VER:-$(cuda_terpasang)}"
    [ -n "$cuda" ] || cuda="13.2"
    [ -d "/usr/local/cuda-$cuda" ] || gagal "/usr/local/cuda-$cuda tidak ada. Cek: ls -d /usr/local/cuda*  lalu CUDA_VER=x.y bash setup_jetson.sh parser"
    info "CUDA_VER=$cuda"
    local dsy="$PROJ_DIR/DeepStream-Yolo"
    [ -d "$dsy" ] || git clone --depth 1 https://github.com/marcoslucianops/DeepStream-Yolo "$dsy"
    export CUDA_VER="$cuda"
    make -C "$dsy/nvdsinfer_custom_impl_Yolo" clean
    make -C "$dsy/nvdsinfer_custom_impl_Yolo" -j"${JOBS:-2}" 2>&1 | grep -E "error|Error|\.so" || true
    [ -f "$dsy/nvdsinfer_custom_impl_Yolo/libnvdsinfer_custom_impl_Yolo.so" ] \
        && ok "Parser siap" \
        || gagal "Compile parser gagal. Lihat error di atas (kirimkan ke pembuat skrip)."
}

# ------------------------------------------------------------------ 6. engine
tahap_engine() {
    judul "6/7 ENGINE TensorRT: yolo26.engine"
    local onnx="$PROJ_DIR/models/yolo26n.onnx" out="$PROJ_DIR/yolo26.engine"
    local ws="${WORKSPACE:-1024}" imgsz="${IMGSZ:-640}" batch="${BATCH:-2}"
    [ -f "$onnx" ] || gagal "models/yolo26n.onnx tidak ada."
    [ -x "$TRTEXEC" ] || gagal "trtexec tidak ada ($TRTEXEC)."
    if [ -s "$out" ] && [ "${ULANG:-0}" != "1" ]; then
        ok "yolo26.engine sudah ada (bangun ulang: ULANG=1 bash setup_jetson.sh engine)"
        return
    fi
    info "FP16, batch 1..$batch, ${imgsz}x${imgsz}, workspace ${ws}MB — 10–30 menit. Jangan dihentikan."
    sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null || true
    local mulai; mulai=$(date +%s)
    "$TRTEXEC" --onnx="$onnx" --saveEngine="$out" --fp16 \
        --minShapes=input:1x3x${imgsz}x${imgsz} \
        --optShapes=input:${batch}x3x${imgsz}x${imgsz} \
        --maxShapes=input:${batch}x3x${imgsz}x${imgsz} \
        --memPoolSize=workspace:${ws}M --skipInference \
        > "$PROJ_DIR/logs_build_engine.txt" 2>&1 || true
    if [ -s "$out" ]; then
        rm -f "$PROJ_DIR"/model_b*_gpu0_*.engine
        ok "yolo26.engine selesai dalam $(( ($(date +%s) - mulai) / 60 )) menit ($(du -h "$out" | cut -f1))"
    else
        tail -n 15 "$PROJ_DIR/logs_build_engine.txt"
        gagal "Build engine gagal. Coba: WORKSPACE=512 bash setup_jetson.sh engine"
    fi
}

# ------------------------------------------------------------------ 7. verifikasi
tahap_verifikasi() {
    judul "7/7 VERIFIKASI"
    bash "$PROJ_DIR/scripts/cek_sistem.sh" || true
    echo
    ok "Setup selesai. Langkah berikutnya:"
    echo "    bash scripts/tes_kamera.sh"
    echo "    $PY scripts/tes_plc.py"
    echo "    HEADLESS=1 PLC_STATE=4 ./run.sh      # uji tanpa PLC"
    echo "    HEADLESS=1 ./run.sh                  # jalan normal dengan PLC"
}

# ------------------------------------------------------------------ main
jalankan() { "tahap_$1"; }

{
    echo "### setup_jetson.sh $(date '+%F %T') args: $*"
    if [ $# -eq 0 ]; then
        for t in "${TAHAP_SEMUA[@]}"; do jalankan "$t"; done
    elif [ "$1" = "--dari" ]; then
        mulai=0
        for t in "${TAHAP_SEMUA[@]}"; do
            [ "$t" = "$2" ] && mulai=1
            [ $mulai -eq 1 ] && jalankan "$t"
        done
        [ $mulai -eq 1 ] || gagal "Tahap '$2' tidak dikenal. Pilihan: ${TAHAP_SEMUA[*]}"
    else
        for t in "$@"; do
            declare -f "tahap_$t" >/dev/null || gagal "Tahap '$t' tidak dikenal. Pilihan: ${TAHAP_SEMUA[*]}"
            jalankan "$t"
        done
    fi
} 2>&1 | tee -a "$LOG"
