FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/root/.cache/huggingface

WORKDIR /app

# System deps for asyncpg / chromadb / sentence-transformers + curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# HuggingFace Spaces uses the SQLite backend — install that requirements file.
# For local Postgres dev, build with --build-arg REQS=requirements.txt.
ARG REQS=requirements.huggingface.txt
COPY requirements.txt requirements.huggingface.txt ./
RUN pip install --upgrade pip && pip install -r ${REQS}

# Pre-download the embedding model so first-request latency in the container is
# not blocked on a HuggingFace download. ~90 MB.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY . .

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
