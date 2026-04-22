#!/bin/bash
# Xbot systemd Setup-Script
# Ausführen als root: sudo bash systemd/setup.sh

set -e

INSTALL_DIR="/opt/xbot"
SERVICE_USER=$(logname 2>/dev/null || echo "$SUDO_USER")

echo "==> Installiere Xbot nach $INSTALL_DIR ..."

# Projektdateien kopieren
mkdir -p "$INSTALL_DIR"
cp -r ./* "$INSTALL_DIR/"
cp .env "$INSTALL_DIR/.env" 2>/dev/null || echo "  Hinweis: .env manuell nach $INSTALL_DIR/.env kopieren!"

# Virtual Environment erstellen
echo "==> Erstelle Virtual Environment ..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# Berechtigungen
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chmod 600 "$INSTALL_DIR/.env" 2>/dev/null || true

# Services installieren (% durch USERNAME ersetzen)
echo "==> Installiere systemd Services ..."
for service in xbot-auto xbot-telegram xbot-web; do
    sed "s/%i/$SERVICE_USER/g" "$INSTALL_DIR/systemd/$service.service" \
        > "/etc/systemd/system/$service.service"
    echo "  Installiert: $service.service"
done

systemctl daemon-reload

echo ""
echo "==> Fertig! Verfügbare Befehle:"
echo ""
echo "  Auto-Modus starten:       sudo systemctl start xbot-auto"
echo "  Auto-Modus aktivieren:    sudo systemctl enable xbot-auto"
echo "  Telegram Bot starten:     sudo systemctl start xbot-telegram"
echo "  Web Dashboard starten:    sudo systemctl start xbot-web"
echo ""
echo "  Logs anzeigen:            sudo journalctl -u xbot-auto -f"
echo "  Status prüfen:            sudo systemctl status xbot-auto"
