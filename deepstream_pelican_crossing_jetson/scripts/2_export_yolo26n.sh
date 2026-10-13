#!/usr/bin/env bash
# LANGKAH 2 — Unduh YOLO26n (.pt) lalu export ke ONNX untuk DeepStream.
#     bash scripts/2_export_yolo26n.sh
#
# Bisa dijalankan di mesin DeepStream ATAU di PC/laptop lain (Linux/WSL)
# yang punya Python 3.9+. Jika di PC lain, salin folder models/ hasilnya
# (yolo26n.onnx + labels.txt) ke folder proyek di mesin DeepStream.
#
# Variabel opsional:
#   MODEL=yolo26s      ganti varian (n/s/m/l/x) atau path model custom tanpa .pt
#   IMGSZ=640          ukuran input
set -e
source "$(dirname "$0")/common.sh"

MODEL="${MODEL:-yolo26n}"
IMGSZ="${IMGSZ:-640}"
MODELS_DIR="$PROJ_DIR/models"
VENV="$PROJ_DIR/.venv-export"
mkdir -p "$MODELS_DIR"

# Skrip export: scripts/export_yolo26_ds.py (versi DeepStream-Yolo yang sudah
# diperbaiki untuk ultralytics & torch terbaru)
EXPORTER="$PROJ_DIR/scripts/export_yolo26_ds.py"
[ -f "$EXPORTER" ] || gagal "scripts/export_yolo26_ds.py tidak ditemukan"

# Virtualenv terpisah supaya torch/ultralytics tidak bentrok dengan pyds
if [ ! -d "$VENV" ]; then
    info "Membuat virtualenv export di $VENV ..."
    python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
pip install -q --upgrade pip
if ! python -c "import torch" 2>/dev/null; then
    info "Memasang PyTorch (versi CPU cukup untuk export)..."
    if [ "$ARCH" = "x86_64" ]; then
        pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
          || pip install torch torchvision
    else
        pip install torch torchvision
    fi
fi
info "Memasang ultralytics + onnx..."
pip install -q -U ultralytics onnx onnxslim onnxruntime onnxscript

cd "$MODELS_DIR"
if [ ! -f "$MODEL.pt" ]; then
    info "Mengunduh $MODEL.pt ..."
    wget -q --show-progress "https://github.com/ultralytics/assets/releases/download/v8.4.0/$MODEL.pt" \
      || python -c "from ultralytics import YOLO; YOLO('$MODEL.pt')"   # fallback: auto-download ultralytics
fi
[ -f "$MODEL.pt" ] || gagal "Gagal mengunduh $MODEL.pt"

info "Export $MODEL.pt -> ONNX (dynamic batch, simplify, size $IMGSZ)..."
rm -f export_yolo26.py   # sisa versi lama
python "$EXPORTER" -w "$MODEL.pt" -s "$IMGSZ" --dynamic --simplify 2>&1 | tee export_log.txt
[ "${PIPESTATUS[0]}" -eq 0 ] || gagal "Export gagal — lihat models/export_log.txt"

# Nama keluaran bisa "<model>.onnx" atau "<model>.pt.onnx" tergantung versi skrip
[ -f "$MODEL.pt.onnx" ] && mv -f "$MODEL.pt.onnx" "$MODEL.onnx"
[ -f "$MODEL.onnx" ] || gagal "File ONNX tidak terbentuk"
[ -f labels.txt ] || warn "labels.txt tidak terbentuk — salin manual (80 kelas COCO)"

deactivate
ok "Selesai: $MODELS_DIR/$MODEL.onnx"
if [ "$MODEL" != "yolo26n" ]; then
    warn "Ubah onnx-file di config_infer_yolo26.txt menjadi models/$MODEL.onnx"
    warn "dan hapus file *.engine lama supaya engine dibangun ulang."
fi
