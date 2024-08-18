import torch
import torch.nn as nn
import torch.nn.functional as F

from ..backbones.det_mobilenet_v3 import ConvBNLayer
from ..common import Activation


class Head(nn.Module):
    def __init__(self, in_channels):
        super().__init__()
        self.conv1 = nn.Conv2d(
            in_channels=in_channels,
            out_channels=in_channels // 4,
            kernel_size=3,
            padding=1,
            bias=False
        )
        self.conv_bn1 = nn.BatchNorm2d(in_channels // 4)
        self.relu1 = Activation(act_type='relu')

        self.conv2 = nn.ConvTranspose2d(
            in_channels=in_channels // 4,
            out_channels=in_channels // 4,
            kernel_size=2,
            stride=2
        )
        self.conv_bn2 = nn.BatchNorm2d(in_channels // 4)
        self.relu2 = Activation(act_type='relu')

        self.conv3 = nn.ConvTranspose2d(
            in_channels=in_channels // 4,
            out_channels=1,
            kernel_size=2,
            stride=2
        )

    def forward(self, x, return_f=False):
        x = self.conv1(x)
        x = self.conv_bn1(x)
        x = self.relu1(x)
        x = self.conv2(x)
        x = self.conv_bn2(x)
        x = self.relu2(x)
        if return_f is True:
            f = x
        x = self.conv3(x)
        x = torch.sigmoid(x)
        if return_f is True:
            return x, f
        return x


class DBHead(nn.Module):
    """
    Differentiable Binarization (DB) for text detection:
        see https://arxiv.org/abs/1911.08947
    args:
        params(dict): super parameters for build DB network
    """

    def __init__(self, in_channels, k=50):
        super().__init__()
        self.k = k
        self.binarize = Head(in_channels)
        self.thresh = Head(in_channels)

    def step_function(self, x, y):
        return torch.reciprocal(1 + torch.exp(-self.k * (x - y)))

    def forward(self, x):
        shrink_maps = self.binarize(x)
        threshold_maps = self.thresh(x)
        if self.training:
            binary_maps = self.step_function(shrink_maps, threshold_maps)
            y = torch.cat((shrink_maps, threshold_maps, binary_maps), dim=1)
        else:
            y = torch.cat((shrink_maps, threshold_maps), dim=1)
        return y


class LocalModule(nn.Module):
    def __init__(self, in_c, mid_c, use_distance=True):
        super(self.__class__, self).__init__()
        self.last_3 = ConvBNLayer(in_c + 1, mid_c, 3, 1, 1, act='relu')
        self.last_1 = nn.Conv2d(mid_c, 1, 1, 1, 0)

    def forward(self, x, init_map, distance_map):
        outf = torch.cat([init_map, x], dim=1)
        # last Conv
        out = self.last_1(self.last_3(outf))
        return out


class PFHeadLocal(DBHead):
    def __init__(self, in_channels, k=50, mode='small', **kwargs):
        super().__init__(in_channels, k)
        self.mode = mode

        self.up_conv = nn.Upsample(scale_factor=2, mode="nearest")
        if self.mode == 'large':
            self.cbn_layer = LocalModule(in_channels // 4, in_channels // 4)
        elif self.mode == 'small':
            self.cbn_layer = LocalModule(in_channels // 4, in_channels // 8)

    def forward(self, x, targets=None):
        shrink_maps, f = self.binarize(x, return_f=True)
        base_maps = shrink_maps
        cbn_maps = self.cbn_layer(self.up_conv(f), shrink_maps, None)
        cbn_maps = F.sigmoid(cbn_maps)
        if not self.training:
            return {'maps': 0.5 * (base_maps + cbn_maps), 'cbn_maps': cbn_maps}

        threshold_maps = self.thresh(x)
        binary_maps = self.step_function(shrink_maps, threshold_maps)
        y = torch.cat([cbn_maps, threshold_maps, binary_maps], dim=1)
        return {'maps': y, 'distance_maps': cbn_maps, 'cbn_maps': binary_maps}
