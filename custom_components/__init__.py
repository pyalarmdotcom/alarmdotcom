"""
Marker file only - not a real Python package at runtime.

Home Assistant's own component loader doesn't care whether this file
exists; it discovers integrations under custom_components/ directly via
each subdirectory's manifest.json, not via a Python import of
`custom_components` itself.

This file exists purely for local tooling (mypy, in particular): without
it, mypy's directory-walk to determine a file's module name stops as soon
as it finds a parent directory *with* its own __init__.py -
custom_components/alarmdotcom/ has one, so mypy would resolve files there
as `alarmdotcom.X` via that walk, while explicit_package_bases + mypy_path
in pyproject.toml separately (and correctly) resolves the same files as
`custom_components.alarmdotcom.X` - two valid resolutions for the same
file, which is exactly the "Source file found twice under different
module names" error. Adding this file lets the directory-walk continue
past alarmdotcom/ to here, landing on the same single resolution the
explicit config already computes.
"""
