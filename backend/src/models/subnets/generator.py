import torch
import torch.nn as nn

from backend.src.models.modules import (
    ActivationFunction,
    SkipConnection,
    Normalization,
    BilinearUpsample,
)


class ConvolutionalBlock(nn.Module):
    def __init__(
        self,
        n_filters,
        expansion_factor,
        kernel_size,
        stride,
        padding,
        groups,
        activation_func,
    ):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(n_filters, n_filters * expansion_factor, 1, 1, 0),
            ActivationFunction(activation_func),
            nn.Conv2d(
                n_filters * expansion_factor,
                n_filters * expansion_factor,
                kernel_size,
                stride,
                padding,
                groups=groups,
            ),
            ActivationFunction(activation_func),
            nn.Conv2d(n_filters * expansion_factor, n_filters, 1, 1, 0, bias=False),
        )

    def forward(self, h, mask=None):
        return self.layers(h)


class GeneratorBlock(nn.Module):
    def __init__(
        self,
        n_filters,
        expansion_factor,
        kernel_size,
        stride,
        padding,
        groups,
        activation_func,
        norm,
    ):
        super().__init__()
        self.module = nn.Sequential(
            BilinearUpsample(2.0),
            SkipConnection(
                ConvolutionalBlock(
                    n_filters,
                    expansion_factor,
                    kernel_size,
                    stride,
                    padding,
                    groups,
                    activation_func,
                )
            ),
            Normalization(n_filters, norm),
            SkipConnection(
                ConvolutionalBlock(
                    n_filters,
                    expansion_factor,
                    kernel_size,
                    stride,
                    padding,
                    groups,
                    activation_func,
                )
            ),
            Normalization(n_filters, norm),
            nn.Conv2d(n_filters, n_filters, kernel_size=1, stride=1, padding=0),
        )

    def forward(self, h, mask=None):
        return self.module(h)


class Generator(nn.Module):
    def __init__(
        self,
        in_dim,
        out_channels,
        n_filters=32,
        expansion_factor=2,
        kernel_size=4,
        stride=2,
        padding=1,
        groups=4,
        n_blocks=3,
        activation_func="leakyrelu",
        norm="batch",
    ):
        super(Generator, self).__init__()
        self.input_layer = nn.Linear(in_dim, n_filters, bias=False)
        self.constant_layer = nn.Parameter(torch.empty(n_filters, 4, 4).normal_(0, 1))
        self.res_block1 = SkipConnection(
            ConvolutionalBlock(
                n_filters,
                expansion_factor,
                kernel_size,
                stride,
                padding,
                groups,
                activation_func,
            )
        )
        self.norm1 = Normalization(n_filters, norm)
        self.res_block2 = SkipConnection(
            ConvolutionalBlock(
                n_filters,
                expansion_factor,
                kernel_size,
                stride,
                padding,
                groups,
                activation_func,
            )
        )
        self.norm2 = Normalization(n_filters, norm)
        self.blocks = nn.ModuleList(
            [
                GeneratorBlock(
                    n_filters,
                    expansion_factor,
                    kernel_size,
                    stride,
                    padding,
                    groups,
                    activation_func,
                    norm,
                )
                for _ in range(n_blocks)
            ]
        )
        self.output_conv = nn.Conv2d(n_filters, out_channels, 4, 1, 0, bias=False)

    def forward(self, x):
        h = self.constant_layer(self.input_layer(x))
        h = self.norm1(self.res_block1(h))
        h = self.norm2(self.res_block2(h))
        for block in self.blocks:
            h = block(h)
        return self.output_conv(h)
