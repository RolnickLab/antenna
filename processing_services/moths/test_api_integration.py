#!/usr/bin/env python3
"""
API Integration Test for Global Moth Classifier Pipeline.
This test calls the actual HTTP API endpoints to validate the service.
"""

import json
import pathlib
import sys
import time

import requests

# Add the processing_services/example to the path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))


def test_api_integration():
    """Test the Global Moth Classifier Pipeline via HTTP API."""
    print("🌐 Testing API Integration for Global Moth Classifier...")
    
    base_url = "http://ml_backend_example:2000"
    
    # Test 1: Get service info
    print("\n📋 Test 1: Getting service info...")
    try:
        response = requests.get(f"{base_url}/info", timeout=30)
        response.raise_for_status()
        info = response.json()
        
        print("✅ Service info retrieved successfully!")
        print(f"   Service name: {info.get('name', 'Unknown')}")
        print(f"   Version: {info.get('version', 'Unknown')}")
        print(f"   Available pipelines: {len(info.get('pipelines', []))}")
        
        # Check if our pipeline is available
        pipeline_slugs = [p.get('slug') for p in info.get('pipelines', [])]
        expected_slug = "zero-shot-object-detector-with-global-moth-classifier-pipeline"
        
        if expected_slug in pipeline_slugs:
            print("✅ Global Moth Classifier pipeline found in service!")
        else:
            print("❌ Global Moth Classifier pipeline NOT found in service")
            print(f"   Available pipelines: {pipeline_slugs}")
            return False
            
    except Exception as e:
        print(f"❌ Service info request failed: {str(e)}")
        return False
    
    # Test 2: Process image with Global Moth Classifier
    print("\n🦋 Test 2: Processing moth image...")
    
    request_payload = {
        "config": {
            "auth_token": "test123",
            "force_reprocess": True,
            "candidate_labels": ["moth", "butterfly", "insect"]
        },
        "pipeline": "zero-shot-object-detector-with-global-moth-classifier-pipeline",
        "source_images": [
            {
                "id": "api_test_123",
                "url": "https://archive.org/download/mma_various_moths_and_butterflies_54143/54143.jpg"
            }
        ]
    }
    
    try:
        print("📤 Sending processing request...")
        print(f"   Pipeline: {request_payload['pipeline']}")
        print(f"   Image URL: {request_payload['source_images'][0]['url']}")
        
        start_time = time.time()
        response = requests.post(
            f"{base_url}/process",
            json=request_payload,
            timeout=300  # 5 minutes timeout for processing
        )
        end_time = time.time()
        
        response.raise_for_status()
        result = response.json()
        
        processing_time = end_time - start_time
        print("✅ Image processed successfully!")
        print(f"   API response time: {processing_time:.2f}s")
        print(f"   Pipeline processing time: {result.get('total_time', 'unknown')}s")
        print(f"   Number of detections: {len(result.get('detections', []))}")
        
        # Analyze results
        detections = result.get('detections', [])
        if detections:
            print("\n🔍 Detection Results:")
            for i, detection in enumerate(detections[:5]):  # Show first 5
                bbox = detection.get('bbox', {})
                classifications = detection.get('classifications', [])
                
                print(f"   Detection {i+1}:")
                print(f"     - Bbox: {bbox}")
                print(f"     - Algorithm: {detection.get('algorithm', {}).get('name', 'unknown')}")
                
                if classifications:
                    # Find top classification
                    top_classification = classifications[0]
                    if 'scores' in top_classification and top_classification['scores']:
                        max_score = max(top_classification['scores'])
                        max_idx = top_classification['scores'].index(max_score)
                        if 'labels' in top_classification and max_idx < len(top_classification['labels']):
                            species_name = top_classification['labels'][max_idx]
                            print(f"     - Top species: {species_name} ({max_score:.3f})")
                        else:
                            print(f"     - Classification: {top_classification.get('classification', 'unknown')}")
            
            if len(detections) > 5:
                print(f"     ... and {len(detections) - 5} more detections")
        else:
            print("⚠️  No detections found in the image")
        
        return True
        
    except Exception as e:
        print(f"❌ Image processing request failed: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_details = e.response.json()
                print(f"   Error details: {json.dumps(error_details, indent=2)}")
            except:
                print(f"   Error response: {e.response.text}")
        return False


def test_service_health():
    """Test basic service health endpoints."""
    print("\n🏥 Testing service health endpoints...")
    
    base_url = "http://ml_backend_example:2000"
    
    # Test health endpoints
    health_endpoints = ["/", "/livez", "/readyz"]
    
    for endpoint in health_endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            response.raise_for_status()
            print(f"✅ {endpoint}: {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint}: {str(e)}")
            return False
    
    return True


if __name__ == "__main__":
    print("🧪 Starting API Integration Tests for Global Moth Classifier")
    print("=" * 60)
    
    # Test service health first
    health_ok = test_service_health()
    if not health_ok:
        print("\n❌ Service health checks failed!")
        sys.exit(1)
    
    # Test main API integration
    api_ok = test_api_integration()
    
    print("\n" + "=" * 60)
    if api_ok:
        print("🎉 All API integration tests PASSED!")
        sys.exit(0)
    else:
        print("❌ API integration tests FAILED!")
        sys.exit(1)