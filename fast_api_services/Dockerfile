FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc g++ curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir setuptools

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/fast_api_services
COPY . /app/fast_api_services/

EXPOSE 8001

CMD ["uvicorn", "fast_api_services.main:app", "--host", "0.0.0.0", "--port", "8001"]
