#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PIL import Image
from src.models import CriteriaConfig, CriteriaType, Threshold
from src.criteria import check_criteria

def test_brightness():
    # Create test criteria
    criteria = CriteriaConfig(
        name="brightness",
        type=CriteriaType.required,
        description="Test brightness",
        threshold=Threshold(min=50, max=250, min_contrast=20)
    )
    
    # Create test image
    mock_image = Image.new('L', (100, 100), color=128)
    pixels = mock_image.load()
    for i in range(50):
        pixels[i, i] = 50  # Dark pixels
        pixels[99-i, i] = 200  # Light pixels
    mock_image = mock_image.convert('L')
    
    print(f"Image size: {mock_image.size}")
    print(f"Image mode: {mock_image.mode}")
    
    # Test image statistics
    from PIL import ImageStat
    stat = ImageStat.Stat(mock_image)
    print(f"Mean brightness: {stat.mean[0]}")
    print(f"Stddev (contrast): {stat.stddev[0]}")
    
    # Test with mock
    from unittest.mock import patch
    with patch('src.criteria._get_images_from_path') as mock_get_images:
        mock_get_images.return_value = [mock_image]
        try:
            result, reason = check_criteria("/fake/path", criteria, "pdf")
            print(f"Result: {result}")
            print(f"Reason: {reason}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_brightness()
