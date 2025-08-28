# syntax=docker/dockerfile:1.7

########################
# Builder
########################
FROM python:3.12-slim AS builder

ARG BACKEND_APP_VERSION=dev
ENV BACKEND_VERSION=$BACKEND_APP_VERSION \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Build deps for native wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
      gcc libc6-dev libffi-dev \
 && rm -rf /var/lib/apt/lists/*

# Install uv
RUN python -m pip install --no-cache-dir uv

WORKDIR /app

# Copy metadata first for better cache
COPY pyproject.toml ./
COPY uv.lock* ./

# Sync only dependencies (no project code yet) into /opt/venv
# Use the lockfile exactly if present
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f uv.lock ]; then \
        uv sync --frozen --no-install-project; \
    else \
        uv sync --no-install-project; \
    fi

# Now copy your code and install the project into the venv (editable)
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen || uv sync

########################
# Runtime
########################
FROM python:3.12-slim AS runtime

ARG BACKEND_APP_VERSION=dev
ENV BACKEND_VERSION=$BACKEND_APP_VERSION \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Only runtime OS deps (+ curl for your healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
      openssh-client sshpass curl \
 && rm -rf /var/lib/apt/lists/*

# SSH relax
RUN sed -i '/#   StrictHostKeyChecking /c StrictHostKeyChecking no' /etc/ssh/ssh_config && \
    sed -i 's/^#\s\+UserKnownHostsFile.*/UserKnownHostsFile \/dev\/null/' /etc/ssh/ssh_config

WORKDIR /app

# Bring the venv from the builder (lives outside /app, so bind mounts won't clobber it)
COPY --from=builder /opt/venv /opt/venv

# Bring app sources (your compose will bind-mount over these in dev)
COPY . .

# Optional tidy
RUN find /app -depth -type d \( -name __pycache__ -o -name tests \) -exec rm -rf '{}' + || true

RUN adduser --disabled-password --gecos '' aurora