# docker/

Container build assets for SupportOps AI.

- `Dockerfile` — builds the FastAPI application image used by `docker-compose.yml`.

TODO:
- Add a separate Dockerfile/target for running Alembic migrations as a one-off job.
- Add a multi-stage production build (slim runtime, non-root user, pinned base image digest).
- Add `.dockerignore` tuning once the dependency set stabilizes.
