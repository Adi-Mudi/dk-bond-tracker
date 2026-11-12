import re
import tomllib
from pathlib import Path

from src.version import APP_VERSION
from src.views import common

ROOT = Path(__file__).resolve().parents[1]


def test_common_reexports_the_single_version_source():
    assert common.APP_VERSION == APP_VERSION


def test_pyproject_matches_the_version_source():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == APP_VERSION


def test_android_version_name_matches_the_version_source():
    gradle = (ROOT / "android" / "app" / "build.gradle").read_text(encoding="utf-8")
    match = re.search(r'versionName\s+"([^"]+)"', gradle)
    assert match, "versionName missing"
    assert match.group(1) == APP_VERSION


def test_product_build_reads_the_version_instead_of_hardcoding_it():
    script = (ROOT / "scripts" / "build_product.sh").read_text(encoding="utf-8")
    assert re.search(r'VERSION="\$\(.*from src\.version import APP_VERSION', script)
    assert 'VERSION="1.0.' not in script


def test_about_page_renders_the_version_source(db_path):
    from src.app import create_app

    app = create_app(str(db_path))
    app.config["TESTING"] = True
    html = app.test_client().get("/about").get_data(as_text=True)
    assert APP_VERSION in html
