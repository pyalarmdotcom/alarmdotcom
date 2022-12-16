#!/usr/bin/env bash

if [ -z "${LIBRARY_NAME}" ] || [ -z "${LIBRARY_GIT_URL}" ] || [ -z "${WORKSPACE_DIRECTORY}" ]; then
  exit 1
else
  library_name="${LIBRARY_NAME}"
  repo_url="${LIBRARY_GIT_URL}"
  lib_dir="/workspaces/$library_name"
  workspace_dir="${WORKSPACE_DIRECTORY}"
fi

cat << EOF

#####################################
INITIALIZING INTEGRATION DEVCONTAINER
#####################################

EOF

container install

cat << EOF

###########################
INSTALLING DEV REQUIREMENTS
###########################

EOF

pip install --upgrade pip
pip install -r "$workspace_dir/requirements-dev.txt"

cat << EOF

#####################
INSTALLING PRE-COMMIT
#####################

EOF

pre-commit install
pre-commit install-hooks

cat << EOF

#################################
INITIALIZING DEVCONTAINER SCRIPTS
#################################

EOF

chmod +x "$workspace_dir/.devcontainer/post-create-script.sh"
chmod +x "$workspace_dir/.devcontainer/post-set-version-hook.sh"
chmod +x "$workspace_dir/.devcontainer/run-hassfest.sh"

cat << EOF

####################################
INITIALIZING LIBRARY "$library_name"
####################################

EOF

if [ ! -d "$lib_dir" ]; then
    echo "Cloning $library_name repository..."
    git clone "$repo_url" "$lib_dir"
else
    echo "$library_name repository directory already exists."
fi

cd "$lib_dir"
python setup.py develop

pip install -r "$lib_dir/requirements-dev.txt"

cat << EOF

#############################
SYMLINKING CONFIGURATION.YAML
#############################

EOF

if test -f ".devcontainer/configuration.yaml"; then
  echo "Copy configuration.yaml"
  ln -sf "$workspace_dir/.devcontainer/configuration.yaml" /config/configuration.yaml || echo ".devcontainer/configuration.yaml are missing"
fi

cat << EOF

##################################
GETTING HOME ASSISTANT SOURCE CODE
##################################

EOF

ha_version=$(pip show homeassistant | grep -Po '^(?:Version\: )(.*)$' | grep -Po '(\d+\.\d+\..*$)')

if [[ "$ha_version" == *"dev"* ]]; then
  ha_version="dev"
fi

"$(workspace_dir)"/.devcontainer/post-set-version-hook.sh "$ha_version"

/workspaces/core/script/setup

cat << EOF

#####
DONE!
#####

EOF

exit 0
