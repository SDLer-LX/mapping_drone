#!/usr/bin/env bash
# Make trigger.py start by itself every time the Jetson powers on.
# Run ON THE JETSON:  bash ~/mapping_drone/setup/install_service.sh   (asks for the sudo password)
#
# Afterwards:
#   tail -f ~/mapping_drone/output/trigger_output.log   # what it is doing
#   sudo systemctl stop mapping-drone               # stop it (before tests that use the camera or Cube)
#   sudo systemctl start mapping-drone              # start it again
#   sudo systemctl disable --now mapping-drone      # turn off auto-start
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

sudo usermod -aG dialout "$USER"
sudo cp "$DIR/mapping-drone.service" /etc/systemd/system/mapping-drone.service
sudo systemctl daemon-reload
sudo systemctl enable mapping-drone.service
sudo systemctl restart mapping-drone.service

# Stop the desktop from auto-mounting (and grabbing) the camera
systemctl --user mask --now gvfs-gphoto2-volume-monitor.service 2>/dev/null || true

sleep 3
systemctl --no-pager --lines=0 status mapping-drone.service | head -5
echo "SERVICE_INSTALLED"
