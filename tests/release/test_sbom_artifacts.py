"""T21: SBOM artifact structure validation.

Skips gracefully if SBOMs not yet generated — run `make sbom` first.
"""

import json
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
SPDX_PATH = REPO_ROOT / "sbom.spdx.json"
CDX_PATH = REPO_ROOT / "sbom.cyclonedx.json"


@pytest.mark.skipif(
    not SPDX_PATH.exists(),
    reason="sbom.spdx.json not found — run `make sbom`",
)
class TestSpdxSbom:
    def test_valid_json(self) -> None:
        data = json.loads(SPDX_PATH.read_text())
        assert isinstance(data, dict)

    def test_spdx_version_present(self) -> None:
        data = json.loads(SPDX_PATH.read_text())
        assert "spdxVersion" in data, "spdxVersion key missing from SPDX SBOM"

    def test_data_license(self) -> None:
        data = json.loads(SPDX_PATH.read_text())
        assert data.get("dataLicense") == "CC0-1.0"

    def test_package_count(self) -> None:
        data = json.loads(SPDX_PATH.read_text())
        packages = data.get("packages", [])
        assert len(packages) > 50, f"Expected >50 packages, got {len(packages)}"

    def test_document_namespace(self) -> None:
        data = json.loads(SPDX_PATH.read_text())
        assert "documentNamespace" in data

    def test_creation_info(self) -> None:
        data = json.loads(SPDX_PATH.read_text())
        assert "creationInfo" in data
        assert "created" in data["creationInfo"]


@pytest.mark.skipif(
    not CDX_PATH.exists(),
    reason="sbom.cyclonedx.json not found — run `make sbom`",
)
class TestCycloneDxSbom:
    def test_valid_json(self) -> None:
        data = json.loads(CDX_PATH.read_text())
        assert isinstance(data, dict)

    def test_bom_format(self) -> None:
        data = json.loads(CDX_PATH.read_text())
        assert data.get("bomFormat") == "CycloneDX"

    def test_spec_version_present(self) -> None:
        data = json.loads(CDX_PATH.read_text())
        assert "specVersion" in data

    def test_component_count(self) -> None:
        data = json.loads(CDX_PATH.read_text())
        components = data.get("components", [])
        assert len(components) > 50, f"Expected >50 components, got {len(components)}"

    def test_metadata_component(self) -> None:
        data = json.loads(CDX_PATH.read_text())
        assert "metadata" in data, "metadata block missing"
        assert "component" in data["metadata"], "metadata.component missing"

    def test_serial_number(self) -> None:
        data = json.loads(CDX_PATH.read_text())
        assert "serialNumber" in data
