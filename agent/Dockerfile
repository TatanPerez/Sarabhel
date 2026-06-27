FROM python:3.11-slim

# create non‑root user
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app

# Install dependencies via pip (no Poetry)
COPY pyproject.toml .
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root
COPY agent.py .

# Drop privileges
USER app
CMD ["python", "agent.py"]