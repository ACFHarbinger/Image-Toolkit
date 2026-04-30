import sys
import os
import cv2
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from backend.src.core.image_merger import ImageMerger

@pytest.fixture
def dummy_images():
    # Create random noise images for better SIFT matching
    np.random.seed(42)
    img1 = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    # img2 is img1 shifted down by 50px
    img2 = np.roll(img1, 50, axis=0)
    
    # Save to temp files
    p1, p2 = "test_img1.png", "test_img2.png"
    cv2.imwrite(p1, img1)
    cv2.imwrite(p2, img2)
    yield [p1, p2]
    # Cleanup
    if os.path.exists(p1): os.remove(p1)
    if os.path.exists(p2): os.remove(p2)

@patch("backend.src.models.gan_wrapper.GanWrapper")
@patch("backend.src.models.siamese_network.SiameseModelLoader.get_embedding")
def test_perfect_stitch_ml_integration(mock_get_embedding, mock_gan, dummy_images):
    # Mock Siamese embedding
    mock_get_embedding.return_value = np.random.rand(512)
    
    # Mock GAN
    mock_g_inst = mock_gan.return_value
    mock_g_inst.generate.side_effect = lambda in_p, out_p: cv2.imwrite(out_p, cv2.imread(in_p))
    
    output = "test_result.png"
    try:
        res = ImageMerger.perfect_stitch(dummy_images, output)
        assert isinstance(res, Image.Image)
        assert os.path.exists(output)
        print("Stitch Success!")
    finally:
        if os.path.exists(output): os.remove(output)

if __name__ == "__main__":
    pytest.main([__file__])
