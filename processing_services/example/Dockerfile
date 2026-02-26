FROM python:3.11-slim

# Install comprehensive OpenGL and X11 dependencies for ML libraries
RUN apt-get update && apt-get install -y \
    libxcb1 \
    libglib2.0-0 \
    libxrender1 \
    libxext6 \
    libsm6 \
    libice6 \
    libgl1-mesa-dri \
    libglx-mesa0 \
    libgl1 \
    mesa-utils \
    libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Set up ml backend FastAPI
WORKDIR /app
COPY . /app
RUN pip install -r ./requirements.txt
CMD ["python", "/app/main.py"]
