#!/usr/bin/env bash

git_dir="/tmp/ver"
dev_dir="/ha-dev"
repo_url="https://github.com/home-assistant/core.git"

if [ -z "$1" ]; then
    echo "No version supplied. Deleting existing development files."
    rm -rf $dev_dir/pylint
    exit 1
fi

mkdir -p "$git_dir"

if [ "$(git -C "$git_dir" config --get remote.origin.url)" == "$repo_url" ]; then
    git -C "$git_dir" checkout tags/"$1"
else
    git clone "$repo_url" --branch "$version" "$git_dir"
fi

mkdir -p "$dev_dir"

if [ "$(readlink "$dev_dir"/pylint)" != "$dev_dir"/pylint ]; then
    ln -sf /tmp/ver/pylint /ha-dev/pylint
fi
