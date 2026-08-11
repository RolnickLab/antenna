#!/usr/bin/env python3
"""
Quick integration test to verify the FlatBugObjectDetector changes work.
"""


def test_flat_bug_integration():
    """Test that the updated FlatBugObjectDetector can be imported and initialized."""
    try:
        # Fix Python path issue for conda environments
        import os
        import sys

        conda_path = "/Users/markfisher/miniconda3/lib/python3.12/site-packages"
        if conda_path not in sys.path and os.path.exists(conda_path):
            sys.path.append(conda_path)

        from api.algorithms import FlatBugObjectDetector

        print("✓ Successfully imported FlatBugObjectDetector")

        # Try to create an instance
        detector = FlatBugObjectDetector()
        print("✓ Created FlatBugObjectDetector instance")

        # Try to compile (this will test our fixes)
        print("Attempting to compile detector...")
        detector.compile(device="cpu")
        print("✓ Successfully compiled FlatBugObjectDetector")

        print("\n✅ All fixes appear to be working correctly!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Testing FlatBugObjectDetector integration...")
    success = test_flat_bug_integration()

    if not success:
        print("\n❌ Integration test failed.")
        print("Check that flat-bug is installed and the fixes are correct.")
    else:
        print("\n🎉 Integration test passed!")
