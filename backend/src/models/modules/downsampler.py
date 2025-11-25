import torch
import torch.nn as nn
import torch.nn.functional as F

from typing import Tuple, Optional


class BilinearDownsample(nn.Module):
    """
    Downsamples a 2D image using bilinear interpolation.
    
    Args:
        scale_factor (float, optional): Multiplier for spatial size (e.g., 0.5 for half size).
                                        Mutually exclusive with size.
        size (tuple, optional): The target output size (H, W).
                                Mutually exclusive with scale_factor.
        align_corners (bool): If True, the corner pixels of the input and output tensors are 
                              aligned, and thus preserving the values at those pixels. 
                              Default: False (standard for image processing).
    """
    def __init__(self, 
                 scale_factor: Optional[float] = None, 
                 size: Optional[Tuple[int, int]] = None, 
                 align_corners: bool = False):
        super().__init__()
        
        if scale_factor is None and size is None:
            raise ValueError("Either scale_factor or size must be provided.")
        if scale_factor is not None and size is not None:
            raise ValueError("Only one of scale_factor or size should be provided.")
            
        self.scale_factor = scale_factor
        self.size = size
        self.align_corners = align_corners

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape expected: (Batch, Channels, Height, Width)
        return F.interpolate(
            x, 
            size=self.size, 
            scale_factor=self.scale_factor, 
            mode='bilinear', 
            align_corners=self.align_corners
        )