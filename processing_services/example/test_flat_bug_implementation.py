#!/usr/bin/env python3
"""
Test script to verify the flat-bug implementation.

This script demonstrates how the FlatBugObjectDetector would work and
highlights any potential adjustments needed for the TensorPredictions format.

To run this test:
1. First install flat-bug: pip install git+https://github.com/darsa-group/flat-bug.git
2. Run: python test_flat_bug_implementation.py
"""


def test_flat_bug_api():
    """Test the flat-bug API to understand the prediction format."""
    try:
        # Fix Python path issue for conda environments
        import os
        import sys

        conda_path = "/Users/markfisher/miniconda3/lib/python3.12/site-packages"
        if conda_path not in sys.path and os.path.exists(conda_path):
            sys.path.append(conda_path)

        import numpy as np
        import torch
        from flat_bug.predictor import Predictor
        from PIL import Image

        print("✓ Successfully imported flat_bug.predictor.Predictor")

        # Create a dummy image for testing - flat-bug expects tensor, not PIL Image
        dummy_image_np = np.ones((480, 640, 3), dtype=np.uint8) * 255  # White image
        dummy_image = torch.from_numpy(dummy_image_np).permute(2, 0, 1).float()  # CHW format
        print(f"✓ Created dummy test image: {dummy_image.shape}")

        # Initialize predictor
        device = "cuda" if torch.cuda.is_available() else "cpu"
        predictor = Predictor(model="flat_bug_M.pt", device=device)
        print(f"✓ Initialized Predictor with device: {device}")

        # Set hyperparameters - DISABLE timing to avoid CUDA event error on CPU
        predictor.set_hyperparameters(
            SCORE_THRESHOLD=0.5, IOU_THRESHOLD=0.5, TIME=False  # CRITICAL: Must be False when running on CPU
        )
        print("✓ Set hyperparameters (timing disabled for CPU compatibility)")

        # Run prediction
        print("Running prediction...")
        predictions = predictor.pyramid_predictions(dummy_image)
        print(f"✓ Prediction completed. Type: {type(predictions)}")

        # Inspect the predictions object - TensorPredictions format
        print("\n--- TensorPredictions Analysis ---")
        print(f"Type: {type(predictions)}")
        print(f"boxes shape: {predictions.boxes.shape if predictions.boxes is not None else None}")
        print(f"confs shape: {predictions.confs.shape if predictions.confs is not None else None}")
        print(f"classes shape: {predictions.classes.shape if predictions.classes is not None else None}")
        print(f"Number of detections: {len(predictions.boxes) if predictions.boxes is not None else 0}")

        # Show sample data
        if predictions.boxes is not None and len(predictions.boxes) > 0:
            print(f"\n--- Sample Detection Data ---")
            print(f"First 3 boxes (xyxy format): {predictions.boxes[:3]}")
            print(f"First 3 confidence scores: {predictions.confs[:3]}")
            print(f"First 3 class IDs: {predictions.classes[:3]}")

            # Convert to format expected by TensorPredictions in Antenna
            print(f"\n--- Format for Antenna Integration ---")
            print(f"Boxes tensor: torch.Tensor of shape {predictions.boxes.shape} (N, 4) in xyxy format")
            print(f"Scores tensor: torch.Tensor of shape {predictions.confs.shape} (N,) confidence scores")
            print(f"Classes tensor: torch.Tensor of shape {predictions.classes.shape} (N,) class indices")

            # Show the data types
            print(f"Boxes dtype: {predictions.boxes.dtype}")
            print(f"Confs dtype: {predictions.confs.dtype}")
            print(f"Classes dtype: {predictions.classes.dtype}")
        else:
            print("\n--- No detections found ---")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please install flat-bug: pip install git+https://github.com/darsa-group/flat-bug.git")
        return False
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False


def show_installation_instructions():
    """Show installation instructions for flat-bug."""
    print("=" * 60)
    print("FLAT-BUG INSTALLATION INSTRUCTIONS")
    print("=" * 60)
    print()
    print("1. Install from source:")
    print("   git clone https://github.com/darsa-group/flat-bug.git")
    print("   cd flat-bug")
    print("   pip install -e .")
    print()
    print("2. Or install directly:")
    print("   pip install git+https://github.com/darsa-group/flat-bug.git")
    print()
    print("3. Make sure PyTorch is installed:")
    print("   pip install torch>=2.3")
    print()
    print("4. The model 'flat_bug_M.pt' will be downloaded automatically")
    print("   on first use.")
    print()


if __name__ == "__main__":
    print("Testing flat-bug implementation...")
    show_installation_instructions()

    success = test_flat_bug_api()

    if success:
        print("\n✅ Test completed successfully!")
        print("The FlatBugObjectDetector implementation should work as expected.")
    else:
        print("\n❌ Test failed.")
        print("You may need to install flat-bug or adjust the implementation.")

    print("\n--- NOTES FOR IMPLEMENTATION ---")
    print("1. The actual attribute names for boxes and scores in TensorPredictions")
    print("   may be different than assumed. Run this test to see the exact format.")
    print("2. You may need to adjust the box format conversion in the run() method.")
    print("3. The flat-bug model will detect arthropods automatically without")
    print("   needing candidate_labels like the zero-shot detector.")
