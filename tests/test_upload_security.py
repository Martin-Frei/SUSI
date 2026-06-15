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
