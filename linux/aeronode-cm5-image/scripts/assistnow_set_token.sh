#!/bin/bash
# Store the Thingstream AssistNow ZTP token on BB1 without echoing it. Readable by node only.
set -u
D=/home/node/.config/aeronode/assistnow
mkdir -p "$D" && chmod 700 "$D"
read -rsp "Paste the AssistNow ZTP token from Thingstream (hidden), then Enter: " T; echo
T=$(printf '%s' "$T" | tr -d '[:space:]')
case "$T" in
  ????????-????-????-????-????????????) ;;
  *) echo "That doesn't look like the 36-character token (got ${#T} characters). Nothing saved; run again."; exit 1;;
esac
umask 077; printf '%s\n' "$T" > "$D/ztp_token"; unset T
echo "Saved ($(wc -c < "$D/ztp_token" | tr -d ' ') bytes) to $D/ztp_token, mode $(stat -c %a "$D/ztp_token"). You can close this tab."
