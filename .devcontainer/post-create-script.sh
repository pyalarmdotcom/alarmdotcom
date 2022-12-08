#!/usr/bin/env bash

container install
pip install --upgrade pip
pip install -r requirements-dev.txt
pre-commit install
pre-commit install-hooks
chmod +x /workspaces/alarmdotcom/.devcontainer/post-set-version-hook.sh

lib_dir="/workspaces/pyalarmdotcomajax"
repo_url="https://github.com/pyalarmdotcom/pyalarmdotcomajax.git"

if [ ! -d $lib_dir ]; then
    echo "Cloning pyalarmdotcomajax repository..."
    git clone "$repo_url" "$lib_dir"
else
    echo "pyalarmdotcomajax repository directory already exists."
fi

cd /workspaces/pyalarmdotcomajax
python setup.py develop

pip install -r /workspaces/pyalarmdotcomajax/requirements-dev.txt
