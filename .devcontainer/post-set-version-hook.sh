#!/usr/bin/env bash

echo "Running HA post-set-version-hook."

git_dir="/tmp/ver"
dev_dir="/workspaces/alarmdotcom"
repo_url="https://github.com/home-assistant/core.git"

if [ -z "$1" ]; then
    echo "No version supplied. Deleting existing development files."
    rm -rf $dev_dir/pylint
    exit 1
fi

mkdir -p "$git_dir"

if [ "$(git -C "$git_dir" config --get remote.origin.url)" == "$repo_url" ]; then
    git -C "$git_dir" fetch
    git -C "$git_dir" checkout tags/"$1"
else
    git clone "$repo_url" --branch "$1" "$git_dir"
fi

mkdir -p "$dev_dir"/pylint/plugins

if [ "$(readlink "$dev_dir"/pylint)" != "$git_dir"/pylint ]; then
    rm -rf "$dev_dir"/pylint/plugins
    cp -r "$git_dir"/pylint/plugins "$dev_dir"/pylint/plugins
fi
