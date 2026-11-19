# Offline check image. Standard library only: nothing is downloaded at run time.
#   docker build -t auditgym .
#   docker run --rm --network none --cpus 2 --memory 4g auditgym
FROM python:3.11.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PYTHONIOENCODING=utf-8

WORKDIR /app
COPY . /app
RUN useradd --create-home --uid 10001 auditor && chown -R auditor:auditor /app
USER auditor

CMD ["python", "-m", "auditgym", "check"]
