import torch.nn as nn

from backend.src.models.modules import (
    ActivationFunction,
    SkipConnection,
    Normalization,
    BilinearDownsample,
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


class DiscriminatorBlock(nn.Module):
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
            BilinearDownsample(0.5),
            nn.Conv2d(n_filters, n_filters, kernel_size=1, stride=1, padding=0),
        )

    def forward(self, h, mask=None):
        return self.module(h)


class Discriminator(nn.Module):
    def __init__(
        self,
        in_channels,
        out_dim,
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
        super(Discriminator, self).__init__()
        self.input_layer = nn.Conv2d(
            in_channels, n_filters, kernel_size=1, stride=1, padding=0
        )
        self.blocks = nn.ModuleList(
            [
                DiscriminatorBlock(
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
        self.output_conv = nn.Conv2d(
            n_filters, n_filters, 4, 1, 0, groups=n_filters, bias=False
        )
        self.linear = nn.Linear(n_filters, out_dim, bias=False)

    def forward(self, x):
        h = self.input_layer(x)
        for block in self.blocks:
            h = block(h)
        h = self.norm1(self.res_block1(h))
        h = self.norm2(self.res_block2(h))
        return self.linear(self.output_conv(h))
