#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="1.0"
NAME="dk_bond_tracker_v${VERSION}"
PRODUCT_DIR="${ROOT}/product/${NAME}"
ZIP_PATH="${ROOT}/product/${NAME}.zip"

if [ ! -f "${ROOT}/requirements.txt" ]; then
  printf 'flask==3.1.3\nopenpyxl==3.1.5\npytest==9.2.0\n' > "${ROOT}/requirements.txt"
fi

rm -rf "${PRODUCT_DIR}"
mkdir -p "${PRODUCT_DIR}/scripts"

cp -R "${ROOT}/src" "${PRODUCT_DIR}/src"
cp -R "${ROOT}/tests" "${PRODUCT_DIR}/tests"
cp "${ROOT}/v5.5_40L_Project_Tracker.xlsm" "${PRODUCT_DIR}/v5.5_40L_Project_Tracker.xlsm"
cp "${ROOT}/requirements.txt" "${PRODUCT_DIR}/requirements.txt"
cp "${ROOT}/scripts/test_local.sh" "${PRODUCT_DIR}/scripts/test_local.sh"
cp "${ROOT}/scripts/test_remote.sh" "${PRODUCT_DIR}/scripts/test_remote.sh"

find "${PRODUCT_DIR}" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "${PRODUCT_DIR}" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

cat > "${PRODUCT_DIR}/setup.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
echo "Setup done. Run ./run.sh to start."
EOF

cat > "${PRODUCT_DIR}/run.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ "${1:-}" = "--empty" ]; then
  exec .venv/bin/python src/app.py --db data/bonds.db
fi
if [ ! -f data/bonds.db ] && [ -f "v5.5_40L_Project_Tracker.xlsm" ]; then
  .venv/bin/python src/app.py --import "v5.5_40L_Project_Tracker.xlsm" --db data/bonds.db
fi
exec .venv/bin/python src/app.py --db data/bonds.db
EOF

cat > "${PRODUCT_DIR}/run.bat" <<'EOF'
@echo off
cd /d "%~dp0"
if "%1"=="--empty" (
  .venv\Scripts\python src\app.py --db data\bonds.db
  pause
  exit /b
)
if not exist data\bonds.db if exist "v5.5_40L_Project_Tracker.xlsm" (
  .venv\Scripts\python src\app.py --import "v5.5_40L_Project_Tracker.xlsm" --db data\bonds.db
)
.venv\Scripts\python src\app.py --db data\bonds.db
pause
EOF

cat > "${PRODUCT_DIR}/README.md" <<'EOF'
# DK Bond Tracker v1.0

Offline bond-tracking dashboard. No accounts, no internet needed after install. Data stays on your machine in data/bonds.db.

## Install (Linux / macOS)

1. Install Python 3.14 from https://www.python.org/downloads/
2. Run setup (creates a virtualenv and installs dependencies):

   ./setup.sh

   If ./setup.sh is blocked, use: bash setup.sh

3. Start the app:

   ./run.sh

   On Windows use run.bat instead.

4. Open http://127.0.0.1:5000 in your browser.

On first run the app imports v5.5_40L_Project_Tracker.xlsm into data/bonds.db automatically.

Start EMPTY instead (fresh database, no data imported - add companies yourself from Watch List): ./run.sh --empty  (Windows: run.bat --empty)

## Email alerts (optional)

Email is off unless you set these environment variables before ./run.sh:

| Variable            | Meaning                          |
| ------------------- | -------------------------------- |
| SMTP_USER           | SMTP login (sender address)      |
| SMTP_APP_PASSWORD   | App password for that account    |
| ALERT_TO            | Recipient (defaults to SMTP_USER)|

## Privacy

Every page has a privacy toggle in the header. It masks money amounts on screen (stored in your browser only; nothing is sent anywhere).

## Tests

Fast tier: ./scripts/test_local.sh
Full tier: ./scripts/test_remote.sh

## Known holds

L1/L2 features are pending and not in this build.
EOF

chmod +x "${PRODUCT_DIR}/setup.sh" "${PRODUCT_DIR}/run.sh"
chmod +x "${PRODUCT_DIR}/scripts/test_local.sh" "${PRODUCT_DIR}/scripts/test_remote.sh"

rm -f "${ZIP_PATH}"
(
  cd "${ROOT}/product"
  zip -r "${NAME}.zip" "${NAME}" -x "*/__pycache__/*" -x "*/__pycache__" -x "*.pyc" -x "*.pyo"
)

echo "Built ${PRODUCT_DIR}"
echo "Zip ${ZIP_PATH}"
