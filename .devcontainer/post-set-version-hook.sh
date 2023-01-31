# File Version: 2023.01.27

#!/usr/bin/env bash

echo "Running HA post-set-version-hook."

if [ -z "${INTEGRATION_NAME}" ] || [ -z "${WORKSPACE_DIRECTORY}" ]; then
  exit 1
else
  integration_name=${INTEGRATION_NAME}
fi

repo_url="https://github.com/home-assistant/core.git"
git_root="/workspaces/core"
workspace_dir="${WORKSPACE_DIRECTORY}"

# Delete integration pylint directory if no version entered.
if [ -z "$1" ]; then
    echo "No version supplied. Deleting existing development files."
    rm -rf "$workspace_dir/pylint"
    exit 1
fi

# Create folder for git repo
mkdir -p "$git_root"

# Fetch requested version from git.
if [ "$(git -C "$git_root" config --get remote.origin.url)" == "$repo_url" ]; then
    git -C "$git_root" fetch
    git -C "$git_root" checkout tags/"$1"
else
    git clone "$repo_url" --branch "$1" "$git_root"
fi

# Move pylint fiiles to integration pylint directory
mkdir -p "$workspace_dir/pylint/plugins"

if [ "$(readlink "$workspace_dir"/pylint\")" != "$git_root/pylint" ]; then
    rm -rf "$workspace_dir/pylint/plugins"
    cp -r "$git_root/pylint/plugins" "$workspace_dir/pylint/plugins"
fi

# Symlink integration's custom_components folder into checked out code to enable hassfest.
if [ "$(readlink "$git_root"/homeassistant/components/"$integration_name")" != "$workspace_dir"/custom_components/"$integration_name" ]; then
    ln -s "$workspace_dir""/custom_components/""$integration_name" "$git_root""/homeassistant/components/""$integration_name"
fi
