#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WAD_DIR="${SCRIPT_DIR}/wad"
OUT_WAD="${WAD_DIR}/doom1.wad"

ZIP_SHA256="cacf0142b31ca1af00796b4a0339e07992ac5f21bc3f81e7532fe1b5e1b486e6"
WAD_SHA256="1d7d43be501e67d927e415e0b8f3e29c3bf33075e859721816f652a526cac771"

URLS=(
  "https://www.doomworld.com/idgames/?file=idstuff/doom/doom19s.zip"
  "https://ftp.fu-berlin.de/pc/msdos/games/idgames/idstuff/doom/doom19s.zip"
  "ftp://ftp.fu-berlin.de/pc/msdos/games/idgames/idstuff/doom/doom19s.zip"
)

sha256_file() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    echo "error: need shasum or sha256sum" >&2
    exit 1
  fi
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: required command not found: $1" >&2
    exit 1
  }
}

need_cmd curl
need_cmd unzip

mkdir -p "${WAD_DIR}"

if [[ -f "${OUT_WAD}" ]]; then
  existing_sha="$(sha256_file "${OUT_WAD}")"
  if [[ "${existing_sha}" == "${WAD_SHA256}" ]]; then
    echo "[doom-wad] already present and valid:"
    echo "  ${OUT_WAD}"
    exit 0
  fi

  echo "[doom-wad] existing wad has unexpected SHA-256; replacing it"
  rm -f "${OUT_WAD}"
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/rfvp-doom-wad.XXXXXX")"
trap 'rm -rf "${TMP_DIR}"' EXIT

ARCHIVE="${TMP_DIR}/doom19s.zip"
INNER_ZIP="${TMP_DIR}/doom19s-inner.zip"
EXTRACTED_WAD="${TMP_DIR}/DOOM1.WAD"

download_ok=0
for url in "${URLS[@]}"; do
  echo "[doom-wad] downloading:"
  echo "  ${url}"

  rm -f "${ARCHIVE}"
  if curl --fail --location --retry 3 --retry-delay 2 \
      --output "${ARCHIVE}" "${url}"; then
    actual_zip_sha="$(sha256_file "${ARCHIVE}")"
    if [[ "${actual_zip_sha}" == "${ZIP_SHA256}" ]]; then
      download_ok=1
      break
    fi

    echo "[doom-wad] downloaded file failed SHA-256 verification" >&2
    echo "  expected: ${ZIP_SHA256}" >&2
    echo "  actual:   ${actual_zip_sha}" >&2
  fi
done

if [[ "${download_ok}" -ne 1 ]]; then
  echo "error: unable to download a verified Doom Shareware 1.9 archive" >&2
  exit 1
fi

echo "[doom-wad] extracting split Shareware payload ..."

# doom19s.zip stores the actual installation archive split into
# DOOMS_19.1 and DOOMS_19.2. Concatenating them reconstructs a ZIP.
unzip -p "${ARCHIVE}" 'DOOMS_19.1' > "${INNER_ZIP}"
unzip -p "${ARCHIVE}" 'DOOMS_19.2' >> "${INNER_ZIP}"

unzip -p "${INNER_ZIP}" 'DOOM1.WAD' > "${EXTRACTED_WAD}"

actual_wad_sha="$(sha256_file "${EXTRACTED_WAD}")"
if [[ "${actual_wad_sha}" != "${WAD_SHA256}" ]]; then
  echo "error: extracted DOOM1.WAD failed SHA-256 verification" >&2
  echo "  expected: ${WAD_SHA256}" >&2
  echo "  actual:   ${actual_wad_sha}" >&2
  exit 1
fi

mv "${EXTRACTED_WAD}" "${OUT_WAD}"

echo "[doom-wad] ready:"
echo "  ${OUT_WAD}"
echo "  SHA-256: ${WAD_SHA256}"
echo
echo "Use it with:"
echo "  python3.11 \"${SCRIPT_DIR}/build.py\" \\"
echo "    \"${SCRIPT_DIR}/DOOM/linuxdoom-1.10\" \\"
echo "    \"${OUT_WAD}\" \\"
echo "    --luax-only"
