"""Tests for how retrieved chunks become the prompt and how citations are checked."""

from ask import build_context, cited_sources


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
