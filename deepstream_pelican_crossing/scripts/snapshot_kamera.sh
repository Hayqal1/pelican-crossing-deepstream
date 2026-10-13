#!/usr/bin/env bash
# Ambil 1 gambar 720x360 dari tiap kamera (resolusi yang sama dengan koordinat
# di config_nvdsanalytics.txt) untuk menentukan posisi ZEBRA dan STOPLINE.
#     bash scripts/snapshot_kamera.sh
# Hasil: snapshot/kam1.jpg, snapshot/kam2.jpg
source "$(dirname "$0")/common.sh"
mkdir -p "$PROJ_DIR/snapshot"

mapfile -t URLS < <(cd "$PROJ_DIR" && python3 - <<'EOF'
import ast, os
tree = ast.parse(open("pelican_deepstream.py").read())
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "SUMBER":
        for el in node.value.elts:
            print(os.environ.get(el.args[0].value, el.args[1].value))
EOF
)

i=1
for url in "${URLS[@]}"; do
    OUT="$PROJ_DIR/snapshot/kam$i.jpg"
    info "KAM$i -> $OUT"
    timeout 20 gst-launch-1.0 -q -e rtspsrc location="$url" protocols=tcp latency=200 ! \
        decodebin ! videoconvert ! videoscale ! video/x-raw,width=720,height=360 ! \
        jpegenc snapshot=true ! filesink location="$OUT" >/dev/null 2>&1
    if [ -s "$OUT" ]; then ok "KAM$i tersimpan"; else warn "KAM$i gagal diambil"; fi
    i=$((i+1))
done
echo
info "Buka gambar di editor (GIMP / Pinta / Paint) — posisi kursor = koordinat x,y."
