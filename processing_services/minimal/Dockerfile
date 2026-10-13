FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install -r ./requirements.txt

# start.sh chooses between FastAPI, worker, or both based on $MODE.
# Default to api (FastAPI push-mode) for backward compatibility with existing CI.
ENV MODE=api
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
