"""Tests for how retrieved chunks become the prompt and how citations are checked."""

import pytest

from ask import build_context, cited_sources, like_pattern, run_tool, search_by_keyword


def chunk(job_id: int, content: str) -> dict:
    return {"job_id": job_id, "content": f"Header {job_id}\n{content}", "title": f"Job {job_id}",
            "company": "Acme", "location": "", "salary": None, "url": f"https://example.com/{job_id}"}


def test_build_context_groups_chunks_by_job_and_drops_headers():
    context = build_context([chunk(7, "Docker"), chunk(7, "Kubernetes"), chunk(3, "Python")])
    assert context.count("<job id=") == 2
    assert '<job id="7"' in context and "Docker\n...\nKubernetes" in context
    assert "Header" not in context
    assert 'location="not stated"' in context


def test_cited_sources_separates_real_and_invented_citations():
    chunks = [chunk(7, "a"), chunk(3, "b")]
    sources, unknown = cited_sources("Acme [job 7] and [job 99], again [job 7].", chunks)
    assert [s["job_id"] for s in sources] == [7]
    assert unknown == [99]


def test_like_pattern_escapes_wildcards():
    assert like_pattern("Docker") == "%Docker%"
    assert like_pattern("50%_off") == "%50\\%\\_off%"


def test_keyword_is_validated_before_touching_the_database():
    with pytest.raises(ValueError):
        search_by_keyword(None, " a ")
    with pytest.raises(ValueError):
        search_by_keyword(None, "x" * 41)


def test_unknown_tool_is_rejected():
    with pytest.raises(ValueError, match="unknown tool"):
        run_tool(None, None, "drop_tables", {})


def test_cited_sources_reads_grouped_citations():
    chunks = [chunk(12, "a"), chunk(34, "b")]
    sources, unknown = cited_sources("Also at TECOPY [job 12, job 34] and [job 12, job 77].", chunks)
    assert [s["job_id"] for s in sources] == [12, 34]
    assert unknown == [77]
