# ./Dockerfile
FROM python:3.12-slim

# (optional) native deps; add others if your libs need them
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m app
WORKDIR /app

# Install deps from pyproject if available; otherwise fall back to minimal
COPY pyproject.toml README.md /app/
# try editable install (PEP 621/517); if that fails, install core libs directly
RUN pip install --no-cache-dir -e . || pip install --no-cache-dir fastmcp duckdb requests

# Copy source code
COPY Source /app/Source

# Helpful runtime envs
ENV PYTHONUNBUFFERED=1 \
    FASTMCP_LOG_LEVEL=INFO

USER app

# We use python as ENTRYPOINT so we can choose the script at `docker run` time
ENTRYPOINT ["python", "-u"]
# Default to Aqueduct MCP if no arg is provided
CMD ["Source/MCP/Aqueduct_Server.py"]
