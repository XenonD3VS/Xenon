#!/usr/bin/env bash
# Builds xenon_mlo-police: generates XML sources and converts them to binary files in ./stream
# Requirements: python3 (numpy, pillow), git, .NET SDK 8+
set -euo pipefail
cd "$(dirname "$0")"

CW_REPO="https://github.com/dexyfex/CodeWalker"

echo "[1/3] Generating XML sources..."
python3 source/generate.py --out source/xml

echo "[2/3] Building converter (CodeWalker.Core)..."
if [ ! -d tools/CodeWalker ]; then
  git clone --depth 1 "$CW_REPO" tools/CodeWalker
fi
dotnet build tools/cwconv/cwconv.csproj -c Release -o tools/cwconv/bin >/dev/null

echo "[3/3] Converting XML -> binary (stream/)..."
dotnet tools/cwconv/bin/cwconv.dll source/xml stream
echo "Done. Copy the xenon_mlo-police folder to your server resources and add: ensure xenon_mlo-police"
