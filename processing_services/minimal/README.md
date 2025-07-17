# Minimal Image Processing Service

A FastAPI-based image processing service with Celery support for asynchronous processing.

## Features

- **FastAPI HTTP API**: Synchronous image processing via REST endpoints
- **Celery Tasks**: Asynchronous image processing via message queues
- **Multiple Pipelines**: Random and Constant pipelines for testing
- **Docker Support**: Multi-service Docker Compose setup
- **Flexible Deployment**: Works with external or local message brokers

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   Celery        │    │   RabbitMQ      │
│   HTTP API      │    │   Worker        │    │   Broker        │
│                 │    │                 │    │                 │
│ /process        │    │ process_pipeline│    │   Queue         │
│ /info           │    │ health_check    │    │                 │
│ /livez          │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Redis         │
                    │   Result        │
                    │   Backend       │
                    └─────────────────┘
```

## Quick Start

### 1. Local Testing with Docker Compose

```bash
# Start with test broker and Redis
docker-compose --profile test up

# Or start individual services
docker-compose --profile test up ml_backend_worker test_rabbitmq test_redis
```

### 2. Production with External Broker

```bash
# Set environment variables
export CELERY_BROKER_URL=amqp://user:pass@external-rabbitmq:5672/vhost
export CELERY_RESULT_BACKEND=redis://external-redis:6379/0

# Start only the worker
docker-compose up ml_backend_worker
```

## Usage

### HTTP API (Synchronous)

```bash
curl -X POST "http://localhost:2000/process" \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline": "random",
    "source_images": [
      {
        "id": "test1",
        "url": "https://example.com/image.jpg"
      }
    ],
    "config": {}
  }'
```

### Celery Tasks (Asynchronous)

#### Submit Job via Script

```bash
python submit_job.py \
  --pipeline random \
  --image-url "https://example.com/image1.jpg" \
  --image-url "https://example.com/image2.jpg" \
  --callback-url "https://your-api.com/results" \
  --broker-url "amqp://guest@localhost:5672//"
```

#### Submit Job Programmatically

```python
from api.tasks import app
from api.schemas import PipelineRequest, SourceImageRequest

# Create request
request = PipelineRequest(
    pipeline="random",
    source_images=[
        SourceImageRequest(id="img1", url="https://example.com/image.jpg")
    ],
    config={}
)

# Submit task
task = app.send_task(
    "api.tasks.process_pipeline",
    args=[request.dict(), "https://callback-url.com/results"]
)

print(f"Task ID: {task.id}")
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Production broker
CELERY_BROKER_URL=amqp://user:password@external-rabbitmq:5672/vhost
CELERY_RESULT_BACKEND=redis://external-redis:6379/0

# Local testing
CELERY_BROKER_URL=amqp://guest@localhost:5672//
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Docker Compose Profiles

- **Default**: API server only
- **test**: Includes local RabbitMQ and Redis for testing

```bash
# Production (external broker)
docker-compose up ml_backend_worker

# Testing (local broker)
docker-compose --profile test up
```

## API Endpoints

- `GET /` - Redirect to API docs
- `GET /info` - Service information and available pipelines
- `GET /livez` - Health check
- `GET /readyz` - Readiness check
- `POST /process` - Synchronous image processing

## Celery Tasks

- `process_pipeline` - Main image processing task
- `health_check` - Worker health check

## Development

### File Structure

```
processing_services/minimal/
├── api/
│   ├── api.py           # FastAPI endpoints
│   ├── tasks.py         # Celery app and tasks
│   ├── processing.py    # Core processing logic
│   ├── pipelines.py     # Pipeline implementations
│   └── schemas.py       # Data models
├── docker-compose.yml   # Multi-service setup
├── Dockerfile          # Container image
├── main.py             # API server entry point
├── start_worker.py     # Celery worker entry point
├── submit_job.py       # Job submission script
└── requirements.txt    # Python dependencies
```

### Adding New Pipelines

1. Create pipeline class in `api/pipelines.py`
2. Add to pipeline registry in `api/processing.py`
3. Update pipeline choice type in `api/schemas.py`

### Result Handling

Results are stored in Redis backend and optionally posted to callback URLs:

```python
# Task returns serialized PipelineResultsResponse
{
    "pipeline": "random",
    "total_time": 1.23,
    "source_images": [...],
    "detections": [...],
    "algorithms": {...}
}
```

## Monitoring

- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Celery Flower**: Add flower to requirements for web monitoring
- **Logs**: Check Docker logs for worker status

## Troubleshooting

### Common Issues

1. **Connection refused**: Check broker URL and network connectivity
2. **Task not found**: Ensure worker is running and task is registered
3. **Serialization errors**: Verify Pydantic models are JSON serializable

### Debug Commands

```bash
# Check worker status
docker-compose logs ml_backend_worker

# Test broker connection
python -c "from api.tasks import app; print(app.control.inspect().stats())"

# Submit test job
python submit_job.py --pipeline random --image-url "https://httpbin.org/image/jpeg"
