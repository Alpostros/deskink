#!/bin/bash
[ "$(id -u)" -eq 0 ] || exec sudo -- bash "$0" "$@"
set -euo pipefail

APP=$(cd "$(dirname "$0")/.." && pwd)
ETC=/etc/deskink
WAVESHARE_SHA=d28b3c4cfc78eef1c6cd6e6e3013654e449d2864

exec > >(tee -a /var/log/deskink-install.log) 2>&1
export DEBIAN_FRONTEND=noninteractive

step() { echo; echo "=== $(date -Is) $*"; }

step preflight
[ "$(uname -m)" = aarch64 ] || echo "WARN: written for 64-bit Raspberry Pi OS, this is $(uname -m)"
CODENAME=$(awk -F= '$1=="VERSION_CODENAME"{print $2}' /etc/os-release)
[ "$CODENAME" = trixie ] || echo "WARN: written for trixie, this is ${CODENAME:-unknown}"
echo "installing from $APP"

step packages
apt-get update
apt-get install -y python3-pil python3-spidev python3-gpiozero python3-lgpio ca-certificates wget git

step spi
raspi-config nonint do_spi 0

step waveshare driver
install -d "$APP/vendor/waveshare_epd"
for f in __init__.py epdconfig.py epd2in13_V4.py; do
    wget -qO "$APP/vendor/waveshare_epd/$f" \
        "https://raw.githubusercontent.com/waveshareteam/e-Paper/$WAVESHARE_SHA/RaspberryPi_JetsonNano/python/lib/waveshare_epd/$f"
done

step user and config
id -u deskink >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d /var/lib/deskink deskink
usermod -aG spi,gpio deskink
install -d -m 755 "$ETC"
if [ ! -f "$ETC/config.toml" ]; then
    install -m 640 -g deskink "$APP/config.example.toml" "$ETC/config.toml"
    echo "created $ETC/config.toml from the example: edit it"
fi
if [ ! -f "$ETC/deskink.env" ]; then
    install -m 600 /dev/null "$ETC/deskink.env"
    echo "NS_API_KEY=" > "$ETC/deskink.env"
    echo "created $ETC/deskink.env: put the NS API key in it"
fi

step wifi power save
if [ -d /etc/NetworkManager/conf.d ]; then
    printf '[connection]\nwifi.powersave = 2\n' > /etc/NetworkManager/conf.d/deskink-wifi-powersave.conf
    echo "wifi power save off from the next reboot"
fi

step service
sed "s|@APP@|$APP|g" "$APP/deploy/deskink.service" > /etc/systemd/system/deskink.service
systemctl daemon-reload
systemctl enable deskink
systemctl restart deskink
sleep 15
systemctl is-active deskink || journalctl -u deskink -n 30 --no-pager
echo
echo "Done. Logs: journalctl -u deskink -f"
