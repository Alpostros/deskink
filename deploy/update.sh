#!/bin/bash
[ "$(id -u)" -eq 0 ] || exec sudo -- bash "$0" "$@"
set -euo pipefail

APP=$(cd "$(dirname "$0")/.." && pwd)
git -C "$APP" pull --ff-only
sed "s|@APP@|$APP|g" "$APP/deploy/deskink.service" > /etc/systemd/system/deskink.service
systemctl daemon-reload
systemctl restart deskink
systemctl is-active deskink
