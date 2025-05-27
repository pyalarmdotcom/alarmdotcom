import argparse
import asyncio
import re
from pathlib import Path
from typing import Literal

import aiohttp
import tomli
import tomli_w
import yaml

# --------------------
# Version Lookup Logic
# --------------------


async def fetch_latest_version(session: aiohttp.ClientSession, package_name: str) -> tuple[str, str | None]:
    """Fetch the latest version of a package from PyPI."""
    package_name_base = package_name.split("[")[0]
    url = f"https://pypi.org/pypi/{package_name_base}/json"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return package_name, data["info"]["version"]
    except Exception:
        pass
    return package_name, None


async def get_latest_versions(package_names: list[str]) -> dict[str, str]:
    """Fetch latest versions for a list of package names."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_latest_version(session, name) for name in package_names]
        results = await asyncio.gather(*tasks)
    return {pkg: version for pkg, version in results if version}


# ----------------------------
# Dependency String Processing
# ----------------------------


def parse_dependency_string(dep: str) -> tuple[str, str, str, Literal["comment", "dependency", "unknown"]]:
    """Extract package name, version, comment, and type."""
    stripped = dep.strip()
    comment = ""
    if "#" in dep:
        dep_part, comment_part = dep.split("#", 1)
        comment = "#" + comment_part.strip()
    else:
        dep_part = dep

    if not dep_part.strip():
        return "", "", comment, "comment"

    match = re.match(r"([a-zA-Z0-9\-_\.]+(\[.+\])?)(\s*[>=<~!^]+\s*)([^#\s]+)?", dep_part)
    if match:
        package_name, _, _, version = match.groups()
        return package_name.strip(), version or "", comment, "dependency"

    return "", "", comment, "unknown"


def update_dependency_line(package: str, new_version: str, comment: str) -> str:
    return f"{package} >= {new_version}{' ' + comment if comment else ''}\n"


# ---------------------
# File Updaters
# ---------------------


async def update_requirements_file(
    path: Path,
    latest_versions: dict[str, str],
    dry_run: bool,
    updates_log: dict[str, list[tuple[str, str, str]]],
) -> None:
    with path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    updated_lines: list[str] = []
    updates: list[tuple[str, str, str]] = []

    for line in lines:
        pkg, old_ver, comment, typ = parse_dependency_string(line)
        if typ == "dependency" and pkg in latest_versions and old_ver != latest_versions[pkg]:
            new_line = update_dependency_line(pkg, latest_versions[pkg], comment)
            updated_lines.append(new_line)
            updates.append((pkg, old_ver, latest_versions[pkg]))
        else:
            updated_lines.append(line)

    updates_log[path.name] = updates
    if not dry_run:
        with path.open("w", encoding="utf-8") as f:
            f.writelines(updated_lines)


async def update_pyproject_toml(
    path: Path,
    latest_versions: dict[str, str],
    dry_run: bool,
    updates_log: dict[str, list[tuple[str, str, str]]],
) -> None:
    with path.open("rb") as f:
        data = tomli.load(f)

    deps = data.get("project", {}).get("dependencies", [])
    new_deps: list[str] = []
    updates: list[tuple[str, str, str]] = []

    for dep in deps:
        pkg, old_ver, comment, typ = parse_dependency_string(dep)
        if typ == "dependency" and pkg in latest_versions and old_ver != latest_versions[pkg]:
            new_deps.append(update_dependency_line(pkg, latest_versions[pkg], comment).strip())
            updates.append((pkg, old_ver, latest_versions[pkg]))
        else:
            new_deps.append(dep)

    if "project" in data:
        data["project"]["dependencies"] = new_deps

    updates_log["pyproject.toml"] = updates
    if not dry_run:
        with path.open("wb") as f:
            tomli_w.dump(data, f)


async def update_pre_commit_config(
    path: Path,
    latest_versions: dict[str, str],
    dry_run: bool,
    updates_log: dict[str, list[tuple[str, str, str]]],
) -> None:
    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    updated = False
    updates: list[tuple[str, str, str]] = []

    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            deps = hook.get("additional_dependencies")
            if deps:
                new_deps = []
                for dep in deps:
                    pkg, old_ver, comment, typ = parse_dependency_string(dep)
                    if typ == "dependency" and pkg in latest_versions and old_ver != latest_versions[pkg]:
                        new_dep = update_dependency_line(pkg, latest_versions[pkg], comment).strip()
                        new_deps.append(new_dep)
                        updates.append((pkg, old_ver, latest_versions[pkg]))
                        updated = True
                    else:
                        new_deps.append(dep)
                hook["additional_dependencies"] = new_deps

    updates_log[".pre-commit-config.yaml"] = updates
    if not dry_run and updated:
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)


# ---------------------
# Main Entry Point
# ---------------------


async def main(directory_path: str, dry_run: bool = False) -> None:
    root = Path(directory_path)
    updates_log: dict[str, list[tuple[str, str, str]]] = {}

    files_to_check = [
        root / "requirements.txt",
        root / "requirements-dev.txt",
        root / "pyproject.toml",
        root / ".pre-commit-config.yaml",
    ]

    pkgs_to_check: set[str] = set()
    for file_path in files_to_check:
        if file_path.exists():
            for line in file_path.read_text(encoding="utf-8").splitlines():
                pkg, _, _, typ = parse_dependency_string(line)
                if typ == "dependency":
                    pkgs_to_check.add(pkg)

    latest_versions = await get_latest_versions(list(pkgs_to_check))

    await update_requirements_file(root / "requirements-dev.txt", latest_versions, dry_run, updates_log)
    await update_pyproject_toml(root / "pyproject.toml", latest_versions, dry_run, updates_log)
    await update_pre_commit_config(root / ".pre-commit-config.yaml", latest_versions, dry_run, updates_log)

    for file, updates in updates_log.items():
        if updates:
            print(f"Updates in {file}:")
            for pkg, old, new in updates:
                print(f" - {pkg}: {old} -> {new}")
        else:
            print(f"No updates needed in {file}.")


# Run with dry-run support
parser = argparse.ArgumentParser()
parser.add_argument("--dir", default="/workspaces/alarmdotcom", help="Project directory path")
parser.add_argument("--dry-run", action="store_true", help="Show changes without modifying files")
args = parser.parse_args()

asyncio.run(main(args.dir, args.dry_run))
