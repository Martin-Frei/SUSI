# Increment 05a — Upload path-traversal fix + ingest cleanup

## Goal

Close the file-upload path-traversal hole in upload_view (the uploaded filename
is used to build the save path unsanitised), and clear the two stale ruff
findings in rag/ingest.py (an unused import and an f-string with no
placeholder). Removing the unused import also drops the langchain-community
dependency, which increment 05b will remove from requirements.

OUT of scope: requirements.txt (increment 05b, done by Claude); the other
boilerplate stub imports across the app.

## Files

- Edit:   `core/views.py`                 (add _safe_filename; use it in upload_view)
- Edit:   `rag/ingest.py`                 (remove unused import; fix f-string)
- Create: `tests/test_upload_security.py` (new tests)

## Required API / behavior

### rag/ingest.py
1. DELETE this unused import line (it is never used):
   ```python
   from langchain_community.document_loaders import TextLoader
   ```
2. Find the print with an f-string that has NO `{}` placeholder:
   ```python
           print(f"  ⚠️  Keine verwertbaren Chunks – Datei übersprungen")
   ```
   Remove the `f` prefix (plain string):
   ```python
           print("  ⚠️  Keine verwertbaren Chunks – Datei übersprungen")
   ```
   Do not change anything else in ingest.py.

### core/views.py — imports
Add to the import block:
```python
from pathlib import Path, PurePosixPath
from django.core.exceptions import SuspiciousFileOperation
from django.utils.text import get_valid_filename
```
(`Path` is already imported — extend that line to also import `PurePosixPath`.)

### core/views.py — new helper
Add this function (place it just above `_ingest_file`):
```python
def _safe_filename(name: str) -> str:
    """Return a safe leaf filename for an upload.

    Strips any directory components (handling both / and \\ separators) so a
    crafted name like '../../etc/passwd' cannot escape the upload directory,
    then validates the leaf. Raises SuspiciousFileOperation for empty, '.' or
    '..' names."""
    leaf = PurePosixPath(name.replace("\\", "/")).name
    return get_valid_filename(leaf)
```

### core/views.py — use it in upload_view
In `upload_view`, replace:
```python
    uploaded = request.FILES["file"]
    filename = uploaded.name
    ext = Path(filename).suffix.lower()
```
with:
```python
    uploaded = request.FILES["file"]
    try:
        filename = _safe_filename(uploaded.name)
    except SuspiciousFileOperation:
        return render(
            request,
            "core/partials/upload_status.html",
            {"success": False, "message": "⚠️ Ungültiger Dateiname."},
        )
    ext = Path(filename).suffix.lower()
```
The rest of upload_view is unchanged; it already builds `temp_path = upload_dir /
filename`, which is now safe because `filename` is a sanitised leaf.

## Tests (no hardware / no external deps)

Create `tests/test_upload_security.py`:
```python
import pytest
from django.core.exceptions import SuspiciousFileOperation

from core.views import _safe_filename


def test_safe_filename_keeps_simple_name():
    assert _safe_filename("report.pdf") == "report.pdf"


def test_safe_filename_strips_posix_traversal():
    out = _safe_filename("../../etc/passwd")
    assert out == "passwd"
    assert "/" not in out and "\\" not in out


def test_safe_filename_strips_windows_traversal():
    out = _safe_filename("..\\..\\windows\\system32\\evil.dll")
    assert out == "evil.dll"
    assert "/" not in out and "\\" not in out


def test_safe_filename_rejects_traversal_only():
    with pytest.raises(SuspiciousFileOperation):
        _safe_filename("../..")
```

## Acceptance

- `ruff check --select F core/views.py rag/ingest.py tests/test_upload_security.py` → 0 findings (this also clears the 2 pre-existing ingest.py findings).
- `pytest -q tests/` → all green (13 prior + 4 new = 17).
- `manage.py test core` → still green.
- `manage.py check` → clean.

## Do NOT

- Do NOT touch requirements.txt (increment 05b).
- Do NOT change other files in rag/ or core/ beyond what is listed.
- Do NOT alter the allowed-extension / max-size checks in upload_view.
- Do NOT add dependencies.
