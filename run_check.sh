#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Синхронизация репозиториев ==="
python3 "$SCRIPT_DIR/scripts/sync_students.py"

echo ""
echo "=== Проверка диаграмм ==="
python3 "$SCRIPT_DIR/scripts/check_diagrams.py"
