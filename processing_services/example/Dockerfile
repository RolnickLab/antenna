FROM python:3.11-slim

# Install minimal X11 dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# Set up ml backend FastAPI
WORKDIR /app
COPY . /app
RUN pip install -r ./requirements.txt
CMD ["python", "/app/main.py"]
