#!/usr/bin/env python3
"""
Test script for the Global Moth Classifier Pipeline.
This test processes a real moth image and validates the full pipeline functionality.
"""

import pathlib
import sys

# Add the processing_services/example to the path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from api.pipelines import ZeroShotObjectDetectorWithGlobalMothClassifierPipeline
from api.schemas import SourceImage
from api.utils import get_image


def test_global_moth_pipeline():
    """Test the Global Moth Classifier Pipeline with a real request."""
    print("🧪 Testing Global Moth Classifier Pipeline with real request...")

    # Create source image from the provided URL
    source_image = SourceImage(
        id="123",
        url="https://archive.org/download/mma_various_moths_and_butterflies_54143/54143.jpg",
        width=800,  # Typical image dimensions
        height=600
    )
    
    # Load the PIL image and attach it to the source image
    print("📥 Loading image from URL...")
    pil_image = get_image(url=source_image.url)
    if pil_image:
        source_image._pil = pil_image
        # Update dimensions with actual image size
        source_image.width = pil_image.width
        source_image.height = pil_image.height
        print(f"✅ Image loaded: {pil_image.width}x{pil_image.height}")
    else:
        print("❌ Failed to load image")
        return False

    # Create pipeline with the test configuration
    pipeline = ZeroShotObjectDetectorWithGlobalMothClassifierPipeline(
        source_images=[source_image],
        request_config={
            "auth_token": "abc123",
            "force_reprocess": True,
            "candidate_labels": ["moth", "butterfly", "insect"]  # Add candidate labels for detection
        },
        existing_detections=[],
    )

    print("✅ Pipeline instantiated successfully!")
    print(f"   Pipeline name: {pipeline.config.name}")
    print(f"   Pipeline slug: {pipeline.config.slug}")
    print(f"   Number of algorithms: {len(pipeline.config.algorithms)}")
    print(f"   Algorithm 1: {pipeline.config.algorithms[0].name}")
    print(f"   Algorithm 2: {pipeline.config.algorithms[1].name}")

    # Test that stages can be created
    stages = pipeline.get_stages()
    assert len(stages) == 2
    print(f"   Stages created: {len(stages)}")

    # Compile the pipeline (load models)
    print("🔧 Compiling pipeline (loading models)...")
    pipeline.compile()
    print("✅ Pipeline compiled successfully!")

    # Run the pipeline
    print("🚀 Running pipeline on test image...")
    try:
        result = pipeline.run()
        print("✅ Pipeline execution completed!")
        print(f"   Total processing time: {result.total_time:.2f}s")
        print(f"   Number of detections: {len(result.detections)}")
        
        # Print detection details
        for i, detection in enumerate(result.detections):
            print(f"   Detection {i+1}:")
            print(f"     - Bbox: {detection.bbox}")
            print(f"     - Inference time: {detection.inference_time:.3f}s")
            print(f"     - Algorithm: {detection.algorithm}")
            if detection.classifications:
                # Get the classification with the highest score
                top_classification = detection.classifications[0]  # Usually sorted by confidence
                if top_classification.scores:
                    max_score = max(top_classification.scores)
                    max_idx = top_classification.scores.index(max_score)
                    if top_classification.labels and max_idx < len(top_classification.labels):
                        species_name = top_classification.labels[max_idx]
                        print(f"     - Top classification: {species_name} ({max_score:.3f})")
                    else:
                        print(f"     - Classification: {top_classification.classification}")
                else:
                    print(f"     - Classification: {top_classification.classification}")
        
        return True
        
    except Exception as e:
        print(f"❌ Pipeline execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_global_moth_pipeline()
