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

################################
INSTALLING GITHUB CLI EXTENSIONS
################################

EOF

gh extension install nektos/gh-act

cat << EOF

###########################
INSTALLING DEV REQUIREMENTS
###########################

EOF

pip install --upgrade pip
pip install -r "$workspace_dir/requirements-dev.txt"

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

(cd "$lib_dir"; python setup.py develop)

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
