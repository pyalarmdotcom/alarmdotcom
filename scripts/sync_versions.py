#!/usr/bin/env python3
"""Script to synchronize dependency versions between config files."""

import json
import re
from pathlib import Path

import yaml


def parse_requirements(req_file: Path) -> dict[str, str]:
    """Parse requirements file and return a dict of package versions."""
    versions: dict[str, str] = {}
    if not req_file.exists():
        return versions

    for raw_line in req_file.read_text().splitlines():
        cleaned_line = raw_line.strip()
        if cleaned_line and not cleaned_line.startswith("#"):
            # Handle different version specifiers
            match = re.match(r"^([^=<>~!]+)[=<>~!]=(.+)$", cleaned_line)
            if match:
                package, version = match.groups()
                versions[package.lower()] = version

    return versions


def parse_manifest(manifest_file: Path) -> dict[str, str]:
    """Parse manifest.json and return a dict of package versions."""
    versions: dict[str, str] = {}
    if not manifest_file.exists():
        return versions

    data = json.loads(manifest_file.read_text())
    for req in data.get("requirements", []):
        # Handle different version specifiers
        match = re.match(r"^([^=<>~!]+)[=<>~!]=(.+)$", req)
        if match:
            package, version = match.groups()
            versions[package.lower()] = version

    return versions


def update_precommit_config(config_file: Path, req_versions: dict[str, str], manifest_versions: dict[str, str]) -> None:
    """Update .pre-commit-config.yaml with synchronized versions."""
    if not config_file.exists():
        return

    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Combine versions, giving precedence to manifest.json
    all_versions = {**req_versions, **manifest_versions}

    modified = False
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            if "additional_dependencies" in hook:
                new_deps = []
                for dep in hook["additional_dependencies"]:
                    # Only process deps that already have a version specified
                    match = re.match(r"^([^=<>~!]+)[=<>~!]=(.+)$", dep)
                    if match:
                        package, current_version = match.groups()
                        package_lower = package.lower()
                        if package_lower in all_versions:
                            new_version = all_versions[package_lower]
                            new_dep = f"{package}>={new_version}"
                            if new_dep != dep:
                                modified = True
                            new_deps.append(new_dep)
                        else:
                            new_deps.append(dep)
                    else:
                        new_deps.append(dep)
                hook["additional_dependencies"] = new_deps

    if modified:
        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        print("Updated .pre-commit-config.yaml with synchronized versions")
    else:
        print("No version updates needed in .pre-commit-config.yaml")


def main() -> None:
    """Synchronize dependency versions between configuration files."""
    workspace_root = Path(__file__).parent.parent

    # Parse requirements-dev.txt
    req_versions = parse_requirements(workspace_root / "requirements-dev.txt")

    # Parse manifest.json
    manifest_versions = parse_manifest(workspace_root / "custom_components" / "alarmdotcom" / "manifest.json")

    # Update .pre-commit-config.yaml
    update_precommit_config(workspace_root / ".pre-commit-config.yaml", req_versions, manifest_versions)


if __name__ == "__main__":
    main()
