FROM python:3.12-slim

WORKDIR /app

# Dependencias del bridge
COPY bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código del bridge y crypto_lib
COPY bridge/ bridge/
COPY crypto_lib/ crypto_lib/

# PYTHONPATH para que bridge.py pueda importar crypto_lib
ENV PYTHONPATH=/app

EXPOSE 5000

CMD ["python3", "bridge/bridge.py"]
