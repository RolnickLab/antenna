FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install -r ./requirements.txt
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
