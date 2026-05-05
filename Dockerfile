# Image Nephos — multi-stage, slim, non-root.
# Build : docker build -t nephos:dev .
# Run   : docker run --rm -e NEPHOS_DATABASE_URL=... nephos:dev nephos --help

ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.5.4

# ---------------------------------------------------------------
# Étage 1 : builder — installe les deps via uv
# ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ARG UV_VERSION

# uv pinné pour reproductibilité.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install --no-install-recommends -y \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

ADD https://astral.sh/uv/${UV_VERSION}/install.sh /uv-install.sh
RUN sh /uv-install.sh && rm /uv-install.sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /build

# Cache des deps en couche distincte pour rebuild rapide.
COPY pyproject.toml uv.lock* README.md ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev || uv sync --no-dev

# ---------------------------------------------------------------
# Étage 2 : runtime — image fine, non-root, sans uv ni build-essential
# ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# Dépendances runtime natives :
# - libpq5 : client PostgreSQL pour psycopg
# - libxml2, libxslt1.1 : lxml (parsing CF XML)
# - ca-certificates : connexions HTTPS aux sources amont
# hadolint ignore=DL3008
RUN apt-get update && apt-get install --no-install-recommends -y \
        libpq5 \
        libxml2 \
        libxslt1.1 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system nephos \
    && useradd --system --gid nephos --create-home --home-dir /home/nephos nephos

WORKDIR /app

# Copie du venv uv (chemin /build/.venv) et du code source.
COPY --from=builder --chown=nephos:nephos /build/.venv /app/.venv
COPY --from=builder --chown=nephos:nephos /build/src /app/src
COPY --chown=nephos:nephos schema_v4_skos.sql /app/
COPY --chown=nephos:nephos alembic.ini /app/
COPY --chown=nephos:nephos alembic /app/alembic

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NEPHOS_LOG_FORMAT=json

USER nephos

ENTRYPOINT ["nephos"]
CMD ["--help"]
