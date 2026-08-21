import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.security import safe_identifier, safe_source_path


def test_identifier_rejects_path_segments():
    with pytest.raises(DomainError):
        safe_identifier("../../etc/passwd", "dataset")


def test_source_path_rejects_unknown_extension(tmp_path):
    p = tmp_path / "bad.pkl"
    p.write_text("x")
    with pytest.raises(DomainError):
        safe_source_path(p, max_bytes=1000)


def test_mcp_source_must_stay_inside_ingest_root(tmp_path):
    from marketing_mcp.security import safe_ingest_path

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    inside = inbox / "ok.csv"
    inside.write_text("a\n1\n")
    outside = tmp_path / "outside.csv"
    outside.write_text("a\n1\n")
    assert safe_ingest_path(inside, inbox, max_bytes=1000) == inside.resolve()
    with pytest.raises(DomainError) as e:
        safe_ingest_path(outside, inbox, max_bytes=1000)
    assert e.value.code == "PATH_NOT_ALLOWED"
