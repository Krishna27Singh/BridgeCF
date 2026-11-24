FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-runtime.txt ./requirements-runtime.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ make ca-certificates \
    && python -m pip install --upgrade pip \
    && python -m pip install -r requirements-runtime.txt \
    && rm -rf /var/lib/apt/lists/*

COPY engine ./backend/engine
COPY app ./backend/app
COPY Makefile ./backend/Makefile

RUN make -C backend \
    && apt-get purge -y g++ make \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid appgroup --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/backend/data \
    && chown -R appuser:appgroup /app

COPY --chown=appuser:appgroup entrypoint.sh /app/backend/entrypoint.sh
RUN chmod 0755 /app/backend/entrypoint.sh

USER appuser
WORKDIR /app/backend

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
