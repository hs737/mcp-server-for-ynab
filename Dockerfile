# MCP Server for YNAB — stdio transport in a container.
#
# The server speaks MCP over stdin/stdout, so the container must be run
# interactively (`-i`) and attached to the client. There is no port to publish;
# `docker run -p` would do nothing.
#
#   docker build -t mcp-server-for-ynab .
#   docker run -i --rm -e YNAB_API_KEY=your_token mcp-server-for-ynab
#
# Writes are off unless you ask for them, exactly as with a local install:
#
#   docker run -i --rm -e YNAB_API_KEY=... -e YNAB_ALLOW_WRITES=1 \
#     -v ynab-mcp-history:/home/app/.mcp-server-for-ynab mcp-server-for-ynab
#
# That volume matters when writes are enabled. The write history is what makes
# a revert possible, and YNAB cannot reproduce it, so leaving it on the
# container's writable layer means every `--rm` throws away the ability to undo.

FROM python:3.12-slim-bookworm AS build

COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Built at the path the runtime stage uses. A virtualenv is not relocatable:
# the console script's shebang is written with an absolute interpreter path, so
# building in /src and copying to /app yields "no such file or directory" on
# every entrypoint invocation.
WORKDIR /app

# Dependencies resolve from the lockfile and cache as their own layer, so a
# source-only change does not reinstall the world.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md LICENSE NOTICE.md ./
COPY src ./src
# --no-editable matters: the default editable install leaves a .pth pointing at
# /app/src, which the runtime stage does not carry, so the package would vanish
# the moment only the venv is copied forward.
RUN uv sync --frozen --no-dev --no-editable


FROM python:3.12-slim-bookworm AS runtime

# Not root: the process holds a credential that can move real money, and
# nothing it does needs privilege.
RUN useradd --create-home --uid 10001 app

COPY --from=build --chown=app:app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
WORKDIR /home/app

# `smoke` validates configuration and tool registration without contacting YNAB,
# which is enough to catch a broken image.
HEALTHCHECK NONE

ENTRYPOINT ["mcp-server-for-ynab"]
CMD ["stdio"]
