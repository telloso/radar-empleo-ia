# Questions about the jobs (RAG)

`collector/ask.py` answers questions in plain language ("¿Qué ofertas en Madrid piden Python e IA generativa?") using only the stored jobs, and cites the jobs it used. It is Retrieval-Augmented Generation where Claude chooses how to search (tool use):

1. **Index** (`collector/embedder.py`, once per new job): each job is cleaned of HTML and split into chunks of 60 words with 15 words of overlap, each starting with the job's title, company and location. Every chunk is turned into a 384-number vector (an *embedding*) and stored in `job_chunks` (`db/init/05-create-job-chunks.sql`) with the [pgvector](https://github.com/pgvector/pgvector) extension.
2. **Retrieve, with tools**: Claude gets two tools and decides which to call, with what words, and how many times:
   - `search_jobs_semantic`: the query is embedded with the same model and PostgreSQL finds the closest chunks by cosine distance (`<=>`). A window function keeps the best two chunks of each job and the six best jobs, so one long offer cannot fill every slot. Good for topics ("cloud infrastructure" also finds AWS).
   - `search_jobs_keyword`: a case-insensitive `ILIKE` over the chunks, with `%` and `_` escaped so the term matches literally. Good for exact names (Docker, Terraform, a company).
3. **Generate**: the search results go back to Claude inside `<job id="N">` tags. The system prompt says to answer only from them, to say so when they do not contain the answer, and to cite every job as `[job N]`. After the answer, the program checks each citation against every job the searches returned, prints the source URLs, and warns about any job cited that no search returned.

The agent loop is written by hand (`ask_claude`): send the question and the tool definitions; while the answer stops with `stop_reason == "tool_use"`, run each requested search and send all results back in one message; stop at `end_turn`. Claude only chooses: the code runs a fixed allow-list of two read-only searches, validates their input, and returns errors as `is_error` tool results so Claude can try another search. The loop is capped at 5 turns, and the last turn sets `tool_choice: none`, so Claude has to answer with what it has; every turn resends the whole conversation, so the cap also caps the cost.

Design choices:

- **Local embeddings** with [fastembed](https://github.com/qdrant/fastembed) and a multilingual model (`paraphrase-multilingual-MiniLM-L12-v2`), because most offers are in Spanish: no API key, no cost per call, and the job texts never leave the machine. The model is downloaded at build time, so the image works offline (it grows to about 1 GB).
- **Why chunks**: the model reads at most 128 tokens (about 80 words). Remotive offers average 650 words of text, so a single vector per job would only see the title and first paragraph.
- **pgvector instead of a separate vector database**: the vectors live next to the jobs they describe, so a plain SQL `JOIN` connects them. With 141 chunks an exact scan takes milliseconds; an HNSW index would be the next step at tens of thousands.
- The `pgvector/pgvector:pg17-trixie` image is used on purpose: it runs on Debian 13 like the previous `postgres:17` image. A Debian 12 build ships an older glibc, whose different text sort order (collation) would put the existing text indexes at risk.

```bash
docker compose build embedder
docker compose run --rm embedder                        # embeds only the jobs not embedded yet
docker compose run --rm ask "¿Alguna oferta pide n8n?"  # needs ANTHROPIC_API_KEY in .env
```

Query 7 in `db/queries.sql` shows the similarity search in plain SQL (jobs closest in meaning to a given one).

Limits worth knowing:

- **Why tool use and not always both searches.** With vector search alone, asking about Docker missed the jobs that mention it: one word barely moves the vector of a 60-word chunk. The keyword tool fixed it (both Docker jobs found and cited). The alternative is *hybrid search*: always run both searches and merge the rankings with a fixed formula (Reciprocal Rank Fusion). That is cheaper and predictable, one Claude call per question; tool use adapts the search to each question (for "generative AI" it searched semantically and for the stem `generativ` at once), at the cost of more calls and less predictable behaviour.
- Claude only sees excerpts, so an answer like "no job asks for X" means "none of the retrieved excerpts do"; the prompt makes it say so.
- The keyword tool matches inside words (`go` also matches "Google"), so the tool description asks for distinctive terms.
- A job whose description changes after it was embedded keeps its old chunks.
- Each question costs about 2-3 cents with Claude Opus 5.5: usually two turns, 2,500-4,000 input tokens.
