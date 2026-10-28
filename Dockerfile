FROM dhi.io/python:3.15-debian13@sha256:4d7b6e0efe27a6ab72462dd6e229e6590f43813fab907ecf3bdcdfc3b41e8a06 as base
FROM dhi.io/python:3.15-debian13-dev@sha256:e1f556371feacccfb5a9d164681228907abcaffd0835683063f22f0e009a8d9d as dev

FROM dev as build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_NO_DEV=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app
COPY uv.lock pyproject.toml .python-version /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv python install

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

COPY . /app

FROM dev AS final

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
ENV STAGE="PRODUCTION"

RUN --mount=type=cache,target=/root/.cache/uv \
--mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
uv python install

COPY --from=build /app /app

CMD ["fastapi", "run", "wealthfolio_converter/api/main.py"]
