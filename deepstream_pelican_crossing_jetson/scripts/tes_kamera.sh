#!/usr/bin/env bash
# Tes koneksi RTSP masing-masing kamera TANPA AI (cek apakah stream bisa dibuka).
#     bash scripts/tes_kamera.sh            -> tes KAM1 dan KAM2 (5 detik masing-masing)
# Mengambil URL langsung dari pelican_deepstream.py (atau env RTSP_KAM1/RTSP_KAM2).
source "$(dirname "$0")/common.sh"

mapfile -t URLS < <(cd "$PROJ_DIR" && python3 - <<'EOF'
import ast, os
src = open("pelican_deepstream.py").read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "SUMBER":
        for i, el in enumerate(node.value.elts):
            env, default = el.args[0].value, el.args[1].value
            print(os.environ.get(env, default))
EOF
)

i=1
for url in "${URLS[@]}"; do
    info "KAM$i: ${url//:*@/:****@}"
    # stream sehat = tetap berjalan sampai di-timeout (kode 124); error = keluar lebih cepat
    if timeout 8 gst-launch-1.0 -q rtspsrc location="$url" protocols=tcp latency=200 \
         ! decodebin ! fakesink sync=false >/dev/null 2>&1; then
        warn "KAM$i berhenti sendiri — cek URL/path stream"
    else
        rc=$?
        if [ $rc -eq 124 ]; then ok "KAM$i stream berjalan (timeout normal)"; else warn "KAM$i GAGAL dibuka — cek IP, user/password, path stream"; fi
    fi
    i=$((i+1))
done
