FROM python:3.11-slim

# create non‑root user
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app

# Install Poetry and project deps
COPY pyproject.toml .
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root

COPY app ./app

# Drop privileges
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]