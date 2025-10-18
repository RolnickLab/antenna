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
        from flat_bug.predictor import Predictor
        from PIL import Image
        import torch
        import numpy as np
        
        print("✓ Successfully imported flat_bug.predictor.Predictor")
        
        # Create a dummy image for testing
        dummy_image = Image.new('RGB', (640, 480), color='white')
        print("✓ Created dummy test image")
        
        # Initialize predictor
        device = "cuda" if torch.cuda.is_available() else "cpu"
        predictor = Predictor(model='flat_bug_M.pt', device=device)
        print(f"✓ Initialized Predictor with device: {device}")
        
        # Set hyperparameters
        predictor.set_hyperparameters(
            SCORE_THRESHOLD=0.5,
            IOU_THRESHOLD=0.5,
            TIME=True  # Enable timing for debugging
        )
        print("✓ Set hyperparameters")
        
        # Run prediction
        print("Running prediction...")
        predictions = predictor.pyramid_predictions(dummy_image)
        print(f"✓ Prediction completed. Type: {type(predictions)}")
        
        # Inspect the predictions object
        print("\n--- Prediction object attributes ---")
        for attr in dir(predictions):
            if not attr.startswith('_'):
                try:
                    value = getattr(predictions, attr)
                    if not callable(value):
                        print(f"{attr}: {type(value)} - {value}")
                except Exception as e:
                    print(f"{attr}: Error accessing - {e}")
        
        # Check for boxes specifically
        if hasattr(predictions, 'boxes') and predictions.boxes is not None:
            print(f"\n--- Boxes found ---")
            boxes = predictions.boxes
            print(f"Boxes type: {type(boxes)}")
            print(f"Boxes shape: {boxes.shape if hasattr(boxes, 'shape') else 'No shape attr'}")
            print(f"Boxes content: {boxes}")
            
            # Convert to numpy if it's a tensor
            if hasattr(boxes, 'cpu'):
                boxes_np = boxes.cpu().numpy()
                print(f"Boxes as numpy: {boxes_np}")
        else:
            print("\n--- No boxes found or boxes is None ---")
            
        # Check for scores
        if hasattr(predictions, 'scores') and predictions.scores is not None:
            print(f"\n--- Scores found ---")
            scores = predictions.scores
            print(f"Scores type: {type(scores)}")
            print(f"Scores content: {scores}")
        else:
            print("\n--- No scores found or scores is None ---")
            
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