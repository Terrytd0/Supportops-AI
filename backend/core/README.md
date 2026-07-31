# backend/core/

Framework-level infrastructure that other parts of `backend/` may depend on,
but that isn't itself business or auth-domain logic.

- `security.py` — the shared `OAuth2PasswordBearer` scheme and the `401`/`403`
  `HTTPException`s auth failures raise. Kept separate from `backend/auth/` so
  any future router can depend on the scheme/exceptions without importing
  the auth package's JWT/hashing internals.
- `logging.py` — `configure_logging()` installs the app's single formatted
  stdout handler (called once, from `backend/main.py`); `get_logger(__name__)`
  is how every other module gets its logger.
- `rate_limit.py` — `limiter` is the shared slowapi `Limiter` instance routes
  decorate with `@limiter.limit(...)`, Redis-backed (`storage_uri=
  settings.redis_url`) with a per-process in-memory fallback if Redis is
  unreachable; `configure_rate_limiting(app)` wires it into the app (called
  once, from `backend/main.py`), including a 429 handler that logs
  throttled requests via `logging.py`. Keys by authenticated user or
  anonymous IP via a resolver `backend.auth` registers at startup
  (`register_key_resolver`) rather than importing `backend.auth.jwt`
  directly here -- see the module docstring for why the dependency has to
  flow that direction.
- `redis_client.py` — `get_redis_client()`, the single place
  `redis.asyncio.Redis` is constructed. Loop-scoped, not process-wide: it
  hands out one client per *calling* event loop (there are legitimately two,
  long-lived, in this app -- FastAPI's own request-handling loop and
  `asyncio_utils.py`'s background loop), since a client's connections are
  bound to whichever loop first uses them and must never be reused from a
  different one. Must be called from inside a running event loop -- see the
  module docstring, and `asyncio_utils.py` below for why.
- `cache.py` — `RedisCache`, a generic namespaced/TTL'd/JSON cache shared by
  `backend.graph.classifier` (ticket classification) and
  `backend.tools.knowledge_base` (knowledge-base retrieval). Fails open: a
  Redis error is treated as a cache miss/no-op, never raised -- caching is a
  pure performance optimization here, unlike idempotency (see
  `backend/services/README.md`). `build_cache_key()` is a module-level
  function (not just `RedisCache.build_key`) so a cache key can be computed
  without needing a `RedisCache` instance -- and so without needing
  `get_redis_client()`, which requires a running event loop.
- `asyncio_utils.py` — `run_sync()`, a sync/async bridge shared by
  synchronous call sites that need to call async repository/service/Redis
  code: `backend.tools.knowledge_base.KnowledgeBaseSearchTool._run` (CrewAI's
  tool interface), `backend.graph.nodes` (`persist_results_node`'s
  supervisor-queue write and the `@_checkpointed` decorator's Redis
  checkpoint save), and `backend.graph.classifier`'s classification cache.
  Always runs the coroutine on one dedicated, process-lifetime background
  event loop (started lazily, in its own daemon thread) rather than a fresh
  `asyncio.run()` per call -- see the module docstring for why a fresh loop
  per call broke `redis.asyncio` usage from inside
  `asyncio.to_thread(get_graph().invoke, ...)`
  (`backend.services.ticket._execute`), and
  `tests/integration/test_ticket_workflow.py` for a real-Redis regression
  test of that failure mode.

## TODO

- [ ] Revisit once `backend/api/middleware/` exists — request-ID/correlation
      helpers and other cross-cutting concerns likely belong here too.
