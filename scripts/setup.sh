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

###########################
INSTALLING DEV REQUIREMENTS
###########################

EOF

pip install --upgrade pip
pip install -r "$workspace_dir/requirements-dev.txt"

cat << EOF

######################################
INITIALIZING HOME ASSISTANT RUN SCRIPT
######################################

EOF

chmod +x $workspace_dir/scripts/run-ha.sh

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

(cd "$lib_dir"; pip install --editable . --config-settings editable_mode=strict)

pip install -r "$lib_dir/requirements-dev.txt"

cat << EOF

#####################
INSTALLING PRE-COMMIT
#####################

EOF

# For integration
pre-commit install
pre-commit install-hooks

# For library
(cd "$lib_dir"; pre-commit install)
(cd "$lib_dir"; pre-commit install-hooks)

cat << EOF

#####
DONE!
#####

EOF

exit 0
