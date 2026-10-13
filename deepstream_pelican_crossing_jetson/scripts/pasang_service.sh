#!/usr/bin/env bash
# Pasang autostart (systemd) untuk program Pelican Crossing.
#     bash scripts/pasang_service.sh          -> pasang & jalankan
#     bash scripts/pasang_service.sh hapus    -> matikan & hapus
set -e
source "$(dirname "$0")/common.sh"
SVC=/etc/systemd/system/pelican-crossing.service

if [ "$1" = "hapus" ]; then
    sudo systemctl disable --now pelican-crossing 2>/dev/null || true
    sudo rm -f "$SVC" && sudo systemctl daemon-reload
    ok "Service dihapus"; exit 0
fi

[ -s "$PROJ_DIR/yolo26.engine" ] || gagal "Selesaikan setup dulu (yolo26.engine belum ada)."
sed -e "s|__USER__|$USER|" -e "s|__DIR__|$PROJ_DIR|g" -e "s|__HOME__|$HOME|" \
    "$PROJ_DIR/pelican-crossing.service" | sudo tee "$SVC" >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now pelican-crossing
ok "Service aktif. Lihat log: journalctl -u pelican-crossing -f"
