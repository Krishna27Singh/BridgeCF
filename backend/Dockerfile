FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ make ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && python -m pip install -r requirements.txt

COPY backend/ ./backend/

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" \
    && make -C backend \
    && mkdir -p /app/backend/data /app/.cache/huggingface \
    && apt-get purge -y g++ make \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN chmod 0755 /app/backend/entrypoint.sh \
    && groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid appgroup --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appgroup /app

USER appuser
WORKDIR /app/backend

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
