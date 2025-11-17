FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install -r ./requirements.txt

RUN chmod +x ./celery_worker/start_celery.sh

CMD ["python", "/app/main.py"]
