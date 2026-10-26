"""Tests for how jobs are cleaned and split into chunks (no model, no database)."""

import embedder
from embedder import chunk_job, html_to_text, to_pgvector


def make_job(description: str) -> dict:
    return {"title": "Python Dev", "company": "Acme", "location": "Madrid", "description": description}


def test_html_to_text_strips_tags_and_entities():
    assert html_to_text("<p>Docker&nbsp;y <b>Python</b></p>") == "Docker y Python"


def test_short_job_is_one_chunk_with_header():
    chunks = chunk_job(make_job("Buscamos perfil junior"))
    assert chunks == ["Python Dev | Acme | Madrid\nBuscamos perfil junior"]


def test_long_job_chunks_overlap_and_cover_every_word():
    words = [f"w{i}" for i in range(130)]
    chunks = chunk_job(make_job(" ".join(words)))
    bodies = [chunk.split("\n", 1)[1].split() for chunk in chunks]

    assert all(len(body) <= embedder.CHUNK_WORDS for body in bodies)
    # The last OVERLAP_WORDS words of a chunk start the next one.
    assert bodies[0][-embedder.OVERLAP_WORDS:] == bodies[1][:embedder.OVERLAP_WORDS]
    assert bodies[-1][-1] == "w129"


def test_to_pgvector_format():
    assert to_pgvector([0.5, -1.0]) == "[0.500000,-1.000000]"
