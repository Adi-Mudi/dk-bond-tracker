#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="1.0"
NAME="dk_bond_tracker_v${VERSION}"
PRODUCT_DIR="${ROOT}/product/${NAME}"
ZIP_PATH="${ROOT}/product/${NAME}.zip"

if [ "${1:-}" = "--check" ]; then
  drift=0
  report() {
    printf '%s\n' "$1"
    drift=1
  }
  if [ ! -d "${PRODUCT_DIR}/src" ]; then
    printf 'MISSING %s/src\n' "${NAME}"
    exit 1
  fi
  while IFS= read -r -d '' f; do
    rel="${f#"${ROOT}/src/"}"
    dst="${PRODUCT_DIR}/src/${rel}"
    if [ ! -f "${dst}" ]; then
      report "MISSING src/${rel}"
    elif ! cmp -s "${f}" "${dst}"; then
      report "DRIFT src/${rel}"
    fi
  done < <(find "${ROOT}/src" -type d -name '__pycache__' -prune -o \( -type f ! -name '*.pyc' ! -name '*.pyo' \) -print0 | sort -z)
  while IFS= read -r -d '' f; do
    rel="${f#"${PRODUCT_DIR}/src/"}"
    if [ ! -f "${ROOT}/src/${rel}" ]; then
      report "EXTRA src/${rel}"
    fi
  done < <(find "${PRODUCT_DIR}/src" -type d -name '__pycache__' -prune -o \( -type f ! -name '*.pyc' ! -name '*.pyo' \) -print0 | sort -z)
  for f in requirements.txt scripts/test_local.sh scripts/test_remote.sh; do
    dst="${PRODUCT_DIR}/${f}"
    if [ ! -f "${dst}" ]; then
      report "MISSING ${f}"
    elif ! cmp -s "${ROOT}/${f}" "${dst}"; then
      report "DRIFT ${f}"
    fi
  done
  if [ "${drift}" -eq 0 ]; then
    printf 'OK no drift\n'
    exit 0
  fi
  exit 1
fi

if [ ! -f "${ROOT}/requirements.txt" ]; then
  printf 'flask==3.1.3\nopenpyxl==3.1.5\npytest==9.2.0\n' > "${ROOT}/requirements.txt"
fi

rm -rf "${PRODUCT_DIR}"
mkdir -p "${PRODUCT_DIR}/scripts"

cp -R "${ROOT}/src" "${PRODUCT_DIR}/src"
cp -R "${ROOT}/tests" "${PRODUCT_DIR}/tests"
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
exec .venv/bin/python src/app.py --db data/bonds.db
EOF

cat > "${PRODUCT_DIR}/run.bat" <<'EOF'
@echo off
cd /d "%~dp0"
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

By default the app starts EMPTY (fresh database, nothing imported) - add companies yourself from Watch List > Add position.

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
