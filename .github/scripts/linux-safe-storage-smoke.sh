#!/usr/bin/env bash
set -euo pipefail

mode="${1:?Usage: linux-safe-storage-smoke.sh <protected|rejected> <app target>}"
target="${2:?Usage: linux-safe-storage-smoke.sh <protected|rejected> <app target>}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
target="$(realpath "$target")"

case "$mode" in
  protected)
    expected_backend=gnome_libsecret
    expected_mode=protected
    password_store=gnome-libsecret
    ;;
  rejected)
    expected_backend=basic_text
    expected_mode=rejected
    password_store=basic
    ;;
  *)
    echo "Unknown safeStorage smoke mode: $mode" >&2
    exit 2
    ;;
esac

temp_dir="$(mktemp -d "${RUNNER_TEMP:-/tmp}/hamartia-keyring-smoke.XXXXXX")"
cleanup() {
  rm -rf -- "$temp_dir" || {
    sleep 0.2
    rm -rf -- "$temp_dir"
  }
}
trap cleanup EXIT
export XDG_CONFIG_HOME="$temp_dir/config"
export XDG_DATA_HOME="$temp_dir/data"
export XDG_CACHE_HOME="$temp_dir/cache"
export XDG_STATE_HOME="$temp_dir/state"
export XDG_RUNTIME_DIR="$temp_dir/runtime"
export XDG_CURRENT_DESKTOP=GNOME
mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$XDG_STATE_HOME" "$XDG_RUNTIME_DIR"
mkdir -p "$XDG_RUNTIME_DIR/keyring"
chmod 700 "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR/keyring"

dbus-run-session -- bash -euo pipefail -s -- "$expected_backend" "$expected_mode" "$password_store" "$repo_root" "$target" <<'SAFE_STORAGE_SESSION'
expected_backend="$1"
expected_mode="$2"
password_store="$3"
repo_root="$4"
target="$5"

keyring_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
keyring_environment="$(printf '%s' "$keyring_password" | gnome-keyring-daemon --unlock --components=secrets --control-directory="$XDG_RUNTIME_DIR/keyring")"
unset keyring_password
eval "$keyring_environment"
unset keyring_environment
case "${GNOME_KEYRING_CONTROL:-}" in
  "$XDG_RUNTIME_DIR"/*) ;;
  *) echo "GNOME keyring control path is outside the temporary runtime directory." >&2; exit 1 ;;
esac
test -d "$GNOME_KEYRING_CONTROL"

export HAMARTIA_ELECTRON_SMOKE_EXPECT_BACKEND="$expected_backend"
export HAMARTIA_ELECTRON_SMOKE_STORAGE_MODE="$expected_mode"
export HAMARTIA_ELECTRON_SMOKE_PASSWORD_STORE="$password_store"
xvfb-run -a node "$repo_root/desktop/smoke_electron.cjs" "$target"
SAFE_STORAGE_SESSION
