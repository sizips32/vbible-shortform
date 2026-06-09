#!/usr/bin/env bash
# ElevenLabs API 키를 화면 노출 없이 ~/.config/hyperframes/.env 에 저장.
# 키는 hidden read 로만 입력받고, argv/transcript 에 절대 남기지 않는다.
set -euo pipefail

env_file="$HOME/.config/hyperframes/.env"
mkdir -p "$(dirname "$env_file")"

printf 'ElevenLabs API key 붙여넣고 Enter (입력 숨김): ' >&2
read -rs key
echo >&2

# strip CR/LF/공백
key="$(printf '%s' "$key" | tr -d '\r\n' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
[ -n "$key" ] || { echo "빈 입력 — 중단." >&2; exit 1; }

tmp="$(mktemp)"
if [ -f "$env_file" ]; then
  grep -v '^ELEVENLABS_API_KEY=' "$env_file" > "$tmp" 2>/dev/null || true
fi
printf 'ELEVENLABS_API_KEY=%s\n' "$key" >> "$tmp"
mv "$tmp" "$env_file"
chmod 600 "$env_file"

printf '저장됨: %s | %s chars | prefix %s\n' "$env_file" "${#key}" "${key:0:3}" >&2
