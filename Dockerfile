FROM python:3.14-slim

LABEL description="Car Maintenance - Application for managing car maintenance schedules"

ARG USERNAME=car-maintenance
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid "$USER_GID" "$USERNAME" \
    && useradd --uid "$USER_UID" --gid "$USER_GID" --create-home "$USERNAME" \
    && mkdir -p /app/data \
    && chown -R "$USERNAME:$USERNAME" /app

WORKDIR /app

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy dependency files first (better Docker layer caching)
COPY pyproject.toml README.md uv.lock* ./

# Copy the Python package early (needed for pip install -e .)
COPY src/ src/

# Install Python dependencies directly in the global Python environment
RUN uv pip install --system -e .

EXPOSE 2662

HEALTHCHECK --interval=300s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; port = '2662'; urllib.request.urlopen(f'http://127.0.0.1:2662/api/v1/health', timeout=2)"

USER ${USERNAME}

CMD ["car-maintenance"]