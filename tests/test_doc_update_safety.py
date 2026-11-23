import pytest
import json
import re
from pathlib import Path

from src.app import create_app
from src.db import init_db

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "docs" / "release_note_template.json"
SIGNING = ROOT / "android" / "SIGNING.md"
LOSS_NORMALISING = re.compile(
    r"(data loss (is|can be|may be) (normal|expected|acceptable|fine|ok)"
    r"|expect (some )?data loss|lose your data is (normal|fine)|normal caveat)",
    re.I,
)


def test_tc_doc_01_release_template_parses_and_carries_required_fields():
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    sections = {section["id"]: section for section in template["sections"]}
    assert "signing_model" in sections
    assert "migration_flow" in sections
    assert "stable release certificate" in sections["signing_model"]["body"]
    assert sections["migration_flow"]["steps"]
    text = TEMPLATE.read_text(encoding="utf-8")
    assert not LOSS_NORMALISING.search(text)


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_tc_doc_01_no_caveat_wording_across_repo_docs():
    for path in (TEMPLATE, SIGNING, ROOT / "src" / "templates" / "about.html"):
        assert not LOSS_NORMALISING.search(
            path.read_text(encoding="utf-8")
        ), f"caveat wording found in {path}"


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_tc_doc_02_about_page_renders_migration_flow(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    client = create_app(str(db_path)).test_client()
    html = client.get("/about").get_data(as_text=True)
    assert 'id="migration-block"' in html
    assert "Uninstall the app." in html
    assert "Install the new release APK." in html
    assert "restore it" in html


def test_tc_doc_03_signing_md_has_leak_backup_and_validity_sections():
    text = SIGNING.read_text(encoding="utf-8")
    assert "## Key leak response" in text
    assert "cannot be revoked" in text
    assert "changing the package name" in text
    assert "## Key backup" in text
    assert "offline copy" in text
    assert "password manager" in text
    assert "## Key validity" in text
    assert "25 years" in text
