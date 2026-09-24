#!/usr/bin/env bash

set -euo pipefail

sudo cp *.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable modep-display.service
sudo systemctl restart modep-display.service
sudo systemctl enable modep-control.service
sudo systemctl restart modep-control.service
