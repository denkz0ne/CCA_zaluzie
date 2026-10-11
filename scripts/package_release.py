"""Build a deterministic HACS archive and reject mismatched release versions."""

import json
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

root = Path(__file__).resolve().parents[1]
component = root / "custom_components/cca_zaluzie"
version = json.loads((component / "manifest.json").read_text(encoding="utf-8"))["version"]
if len(sys.argv) != 2 or sys.argv[1] != version:
    raise SystemExit(f"Tag must match manifest version {version}")
dest = root / "dist"
dest.mkdir(exist_ok=True)
with ZipFile(dest / "cca_zaluzie.zip", "w", compression=ZIP_DEFLATED) as archive:
    for name in ("LICENSE", "ATTRIBUTION.md"):
        info = ZipInfo(name, (2026, 10, 11, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        archive.writestr(info, (root / name).read_bytes())
    for path in sorted(component.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            info = ZipInfo(path.relative_to(component).as_posix(), (2026, 10, 11, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
with ZipFile(dest / "cca_zaluzie.zip") as archive:
    assert "manifest.json" in archive.namelist()
    assert "frontend/cca-zaluzie-panel.js" in archive.namelist()
    assert json.loads(archive.read("manifest.json"))["version"] == version
changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
sections = changelog.splitlines(keepends=True)
start = next(
    (i for i, line in enumerate(sections) if line.strip() == f"# {version}"), None
)
if start is None:
    raise SystemExit(f"CHANGELOG.md has no section for {version}")
end = next(
    (i for i in range(start + 1, len(sections)) if sections[i].startswith("# ")),
    len(sections),
)
(dest / "RELEASE_NOTES.md").write_text("".join(sections[start:end]), encoding="utf-8")
print(f"Built cca_zaluzie.zip for {version}")
