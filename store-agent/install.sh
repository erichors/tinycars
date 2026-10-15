#!/usr/bin/env bash
# Install the TinyCars store agent on an Ubuntu/Debian VM (run as root: sudo ./install.sh).
# Usage: sudo STOREFRONT_URL=http://<storefront-address> ./install.sh
# Optional: TINYCARS_OTEL=1 also installs OpenTelemetry Python auto-instrumentation so the POS
# traffic shows up as traces (sent to the local Bindplane collector on localhost:4318).
set -euo pipefail

STOREFRONT_URL="${STOREFRONT_URL:?set STOREFRONT_URL, e.g. http://my-elb.us-east-1.elb.amazonaws.com}"
ADMIN_TOKEN="${ADMIN_TOKEN:-tinycars}"
INSTALL_DIR=/opt/tinycars
LOG_DIR=/var/log/tinycars

apt-get update -y
apt-get install -y python3 python3-venv tzdata

id tinycars &>/dev/null || useradd --system --home "$INSTALL_DIR" --shell /usr/sbin/nologin tinycars
mkdir -p "$INSTALL_DIR" "$LOG_DIR" /etc/tinycars
install -m 0755 "$(dirname "$0")/agent.py" "$INSTALL_DIR/agent.py"
# world-readable so the Bindplane collector user can tail the logs
chown -R tinycars:tinycars "$INSTALL_DIR" "$LOG_DIR"
chmod 0755 "$LOG_DIR"

python3 -m venv "$INSTALL_DIR/venv"
START="$INSTALL_DIR/venv/bin/python $INSTALL_DIR/agent.py"
if [ "${TINYCARS_OTEL:-0}" = "1" ]; then
  "$INSTALL_DIR/venv/bin/pip" install --quiet opentelemetry-distro opentelemetry-exporter-otlp
  "$INSTALL_DIR/venv/bin/opentelemetry-bootstrap" -a install
  START="$INSTALL_DIR/venv/bin/opentelemetry-instrument $INSTALL_DIR/venv/bin/python $INSTALL_DIR/agent.py"
fi

cat > /etc/tinycars/agent.env <<EOF
STOREFRONT_URL=$STOREFRONT_URL
ADMIN_TOKEN=$ADMIN_TOKEN
LOG_DIR=$LOG_DIR
# Optional OTel (used when TINYCARS_OTEL=1): the Bindplane collector on this VM listens on 4318
OTEL_SERVICE_NAME=store-pos
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_RESOURCE_ATTRIBUTES=service.namespace=tinycars,deployment.environment=demo,host.role=store-pos
OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=false
EOF

cat > /etc/systemd/system/tinycars-store-agent.service <<EOF
[Unit]
Description=TinyCars store agent (Boston, Chicago, London)
After=network-online.target
Wants=network-online.target

[Service]
User=tinycars
EnvironmentFile=/etc/tinycars/agent.env
ExecStart=$START
Restart=always
RestartSec=5
# files created readable by others so the collector can tail them
UMask=0022

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now tinycars-store-agent
echo "Done. Logs: $LOG_DIR/{boston,chicago,london}/{store,security,audit}.log"
echo "Status: systemctl status tinycars-store-agent"
