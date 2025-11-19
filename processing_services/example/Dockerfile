FROM python:3.11-slim

# Set up ml backend FastAPI
WORKDIR /app
COPY . /app
RUN pip install -r ./requirements.txt
CMD ["python", "/app/main.py"]
