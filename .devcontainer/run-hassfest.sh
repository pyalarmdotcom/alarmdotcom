#!/usr/bin/env bash

echo "Running hassfest."

if [[ -z "${INTEGRATION_NAME}" ]] || [[ -z "${WORKSPACE_DIRECTORY}" ]]; then
  exit 1
fi

/workspaces/core/script/run-in-env.sh python3 -m script.hassfest --action validate --integration-path ${WORKSPACE_DIRECTORY}/custom_components/${INTEGRATION_NAME} -p application_credentials,bluetooth,codeowners,dependencies,dhcp,json,manifest,mqtt,services,ssdp,translations,usb,zeroconf,config_flow,coverage,mypy_config,metadata
