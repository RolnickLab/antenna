FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY . /app

RUN pip install -r ./requirements.txt && \
    mkdir -p /tmp/celery-results && \
    chmod 777 /tmp/celery-results

CMD ["python", "/app/main.py"]
