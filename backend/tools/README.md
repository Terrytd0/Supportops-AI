# backend/tools/

Tool implementations exposed to agents (e.g. CRM/billing system lookups,
ticketing system integration, knowledge base search). Agents in
`backend/agents/` consume these rather than implementing raw integrations
inline.

## `knowledge_base.py` — `KnowledgeBaseSearchTool`

A lightweight RAG (retrieval-augmented generation) mechanism: retrieve
relevant `knowledge_articles` rows and feed them into the specialist
agent's prompt as grounding context, the same retrieve-then-generate
pattern RAG describes generally. "Lightweight" specifically means: ranking
is plain keyword overlap between the query and article text
(`KnowledgeArticleRepository.search`), not vector/embedding similarity, over
a small, category-scoped Postgres table -- no vector store, no chunking.
That's an appropriate match for the current dataset (`backend/scripts
/seed.py`'s ~10 articles per category); embeddings would earn their keep if
the knowledge base grows large enough that keyword overlap stops ranking
well.

A `crewai.tools.BaseTool` subclass -- CrewAI's own tool interface is the
"common tool interface" every tool here should implement, so agents can
register and invoke tools uniformly without a bespoke abstraction.

One instance is constructed per agent, bound to that agent's `category`
(only `query` is exposed in the LLM-facing schema). `_run` first checks a
Redis cache (`backend.core.cache.RedisCache`, keyed by category + normalized
query) before calling
`backend.database.repositories.knowledge_article.KnowledgeArticleRepository`
via `backend.core.asyncio_utils.run_sync` (a shared sync/async bridge --
`crewai.tools.BaseTool._run` is synchronous, but repository access is
async-only; `backend/graph/nodes.py` uses the same bridge for its own
synchronous audit-logging/persistence/checkpoint calls), and never raises: a
DB failure or empty result returns a clear, human-readable message instead
of propagating an exception, per the workflow's "never crash" requirement.
Only a genuinely successful search (results, or legitimately none) is
cached -- a DB-unavailable failure is not, so an outage is always retried
rather than semi-permanently cached as "no knowledge available."

## TODO

- [ ] Implement billing system lookup tool
- [ ] Implement ticketing/CRM tool
