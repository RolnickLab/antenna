#!/usr/bin/env python3
"""
Simple test to trigger model compilation and see enhanced logging.
"""

import pathlib
import sys

# Add the processing_services/example to the path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from api.global_moth_classifier import GlobalMothClassifier


def test_compilation_logging():
    """Test the enhanced logging during model compilation."""
    print("🔧 Testing enhanced compilation logging...")
    
    # Create classifier instance
    classifier = GlobalMothClassifier()
    
    print(f"📋 Classifier instantiated: {classifier.name}")
    print(f"   Expected classes: {classifier.num_classes}")
    
    # Trigger compilation (this should show our enhanced logging)
    print("\n⚡ Triggering compilation...")
    classifier.compile()
    
    print("\n✅ Compilation complete!")
    print(f"   Model loaded: {classifier.model is not None}")
    print(f"   Transforms ready: {classifier.transforms is not None}")
    print(f"   Categories loaded: {len(classifier.category_map)} species")
    
    return True


if __name__ == "__main__":
    test_compilation_logging()