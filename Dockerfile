FROM python:3.11-slim

ARG INSTALL_DEV=0

WORKDIR /app

# Install system deps for psycopg2
RUN apt-get update && apt-get install -y     gcc libpq-dev     && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching: only re-runs if requirements change).
# Runtime image gets requirements.txt only; compose sets INSTALL_DEV=1 for local tests.
COPY requirements.txt requirements-dev.txt ./
RUN if [ "$INSTALL_DEV" = "1" ]; then pip install --no-cache-dir -r requirements-dev.txt;     else pip install --no-cache-dir -r requirements.txt; fi

# Copy application code
COPY . .

# Non-root runtime user; models/ and features/ must be writable for local boot-time training
RUN chmod +x entrypoint.sh     && mkdir -p models features     && useradd --system --no-create-home app     && chown -R app /app/models /app/features
USER app

EXPOSE 8000

# Use entrypoint script so we can run setup before server starts
CMD ["sh", "entrypoint.sh"]
