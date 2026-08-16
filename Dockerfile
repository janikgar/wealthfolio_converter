FROM dhi.io/python:3.14.7-debian13@sha256:0536ccad57c9be08128bd2a6f0982570086ec943a88033f4f53f7adffe407903 as base
FROM dhi.io/python:3.14.7-debian13-dev@sha256:02173cae8b920c98ff9fab81eb1aefcadd229f158110553c6ed758dc935589dd AS dev

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
