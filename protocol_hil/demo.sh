#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")" && pwd)"
session_name="caiman-hil-demo"
ensta_paused=false

if [[ "${TERM:-dumb}" == "dumb" ]]; then
    export TERM=xterm-256color
fi

if ! command -v tmux >/dev/null 2>&1; then
    echo "Erro: tmux não está instalado." >&2
    exit 1
fi
# Dedicate the physical Wi-Fi radio to HIL when Ethernet is online.
if ip -4 route show default | grep -q "dev eth0" &&
   nmcli -t -f NAME connection show --active | grep -qx "ensta-maison"; then
    sudo -n nmcli connection down ensta-maison
    ensta_paused=true
fi

if ! nmcli -t -f NAME connection show --active | grep -qx "caiman-hil"; then
    sudo -n nmcli connection up caiman-hil ifname wlan0
fi

cleanup() {
    tmux kill-session -t "$session_name" 2>/dev/null || true
    if [[ "$ensta_paused" == true ]]; then
        sudo -n nmcli connection down caiman-hil >/dev/null 2>&1 || true
        sudo -n nmcli connection up ensta-maison ifname wlan1 >/dev/null || true
    fi
}
trap cleanup EXIT INT TERM HUP

tmux kill-session -t "$session_name" 2>/dev/null || true
tmux new-session -d -s "$session_name" -c "$project_root" \
    "bash -lc 'printf \"\033[1;36mESP32/R1 — publicação de telemetria\033[0m\n\"; ./build/caiman_esp_log 4211'"
tmux split-window -h -t "$session_name" -c "$project_root" \
    "bash -lc 'printf \"\033[1;33mRASPBERRY/BASE — telemetria autenticada\033[0m\n\"; ./build/caiman_pi 192.168.4.1 4210'"
tmux select-layout -t "$session_name" even-horizontal >/dev/null
tmux set-option -t "$session_name" status-style "bg=colour234,fg=colour46"
tmux set-option -t "$session_name" status-left " CAIMAN HIL "
tmux attach-session -t "$session_name"
