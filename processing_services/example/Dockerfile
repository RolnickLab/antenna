FROM python:3.11-slim

# Set up environment for Darsa Group flat-bug
RUN apt-get update && apt-get install -y \
    git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/darsa-group/flat-bug.git /opt/flat-bug
RUN cd /opt/flat-bug && pip install -e .

# Set up ml backend FastAPI
WORKDIR /app
COPY . /app
RUN pip install -r ./requirements.txt
CMD ["python", "/app/main.py"]
