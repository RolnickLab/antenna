#!/usr/bin/env python3
"""
Celery worker startup script for image processing.
"""

import logging

from api.tasks import app

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Start the Celery worker
    app.worker_main(
        [
            "worker",
            "--loglevel=info",
            "--concurrency=1",
            "--pool=solo",  # Use solo pool for better compatibility
        ]
    )
