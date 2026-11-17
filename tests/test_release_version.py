"""Keep release metadata aligned between the integration and bundled library."""

import json
from pathlib import Path

from custom_components.alarmdotcom import _pyalarmdotcomajax as pyadc


def test_bundled_library_version_matches_manifest():
    """A release bump must update the version reported by the bundled library."""
    manifest_path = Path(__file__).parents[1] / "custom_components" / "alarmdotcom" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert pyadc.__version__ == manifest["version"]
