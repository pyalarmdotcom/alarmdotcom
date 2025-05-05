#!/usr/bin/env bash

# ─── Fail Fast Settings ────────────────────────────────────────────────────────
set -Eeuo pipefail
trap 'echo -e "\n❌ Error on line $LINENO. Exiting."; exit 1' ERR

# ─── Command Wrapper ───────────────────────────────────────────────────────────
check_command() {
    echo -e "\n🔹 Running: \033[1;36m$*\033[0m"
    "$@"
}

# ─── Input Validation ──────────────────────────────────────────────────────────
if [[ -z "${LIBRARY_NAME}" || -z "${LIBRARY_GIT_URL}" || -z "${WORKSPACE_DIRECTORY}" ]]; then
    echo "❌ One or more required environment variables are missing: LIBRARY_NAME, LIBRARY_GIT_URL, WORKSPACE_DIRECTORY"
    exit 1
fi

library_name="${LIBRARY_NAME}"
repo_url="${LIBRARY_GIT_URL}"
lib_dir="/workspaces/$library_name"
workspace_dir="${WORKSPACE_DIRECTORY}"

# ─── Home Assistant Prerequisites ──────────────────────────────────────────────
echo -e "\n\033[1;34m==> Installing Home Assistant prerequisites...\033[0m"

check_command sudo apt-get update
check_command sudo apt-get upgrade -y
check_command sudo apt-get install -y \
    python3 python3-dev python3-venv python3-pip \
    bluez libffi-dev libssl-dev libjpeg-dev zlib1g-dev autoconf build-essential \
    libopenjp2-7 libtiff6 libturbojpeg0-dev tzdata ffmpeg liblapack3 \
    liblapack-dev libatlas-base-dev

# ─── Optional: go2rtc binary (for streaming support) ───────────────────────────
echo -e "\n\033[1;34m==> Installing go2rtc for optional streaming support...\033[0m"

check_command wget https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_amd64
check_command chmod +x go2rtc_linux_amd64
check_command sudo mv go2rtc_linux_amd64 /usr/local/bin/go2rtc
check_command go2rtc --version

# ─── Dev Requirements ──────────────────────────────────────────────────────────
echo -e "\n\033[1;34m==> Installing Python dev requirements...\033[0m"

check_command pip install --upgrade pip
check_command pip install -r "$workspace_dir/requirements-dev.txt"

# ─── Home Assistant Script ─────────────────────────────────────────────────────
echo -e "\n\033[1;34m==> Making Home Assistant script executable...\033[0m"

check_command chmod +x "$workspace_dir/scripts/run-ha.sh"

# ─── Initialize Library ────────────────────────────────────────────────────────
echo -e "\n\033[1;34m==> Initializing library: $library_name\033[0m"

if [ ! -d "$lib_dir" ]; then
    echo -e "\n📥 Cloning $library_name repository..."
    check_command git clone "$repo_url" "$lib_dir"
else
    echo -e "\n📁 $library_name repository directory already exists."
fi

check_command pip install --editable "$lib_dir" --config-settings editable_mode=strict
check_command pip install -r "$lib_dir/requirements-dev.txt"

# ─── Pre-commit Hooks ──────────────────────────────────────────────────────────
echo -e "\n\033[1;34m==> Installing pre-commit hooks...\033[0m"

check_command pre-commit install
check_command (cd "$lib_dir" && pre-commit install)

# ─── Done ──────────────────────────────────────────────────────────────────────
echo -e "\n\033[1;32m✅ Setup complete. You’re ready to go!\033[0m"

exit 0
