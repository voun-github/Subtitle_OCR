# Subtitle OCR

![python version](https://img.shields.io/badge/Python-3.12-blue)

Program that uses deep learning to detect and recognize texts.
The training data is optimized for subtitle text images.

## Training Setup Instructions

### Download and Install:

[Latest Version of Microsoft Visual C++ Redistributable](https://learn.microsoft.com/en-US/cpp/windows/latest-supported-vc-redist)

### Install Packages:

For GPU

```
pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu124
```

For CPU and/or Other Packages

```commandline
pip install -r requirements.txt
```

### Build Package:

```commandline
python -m build
```

## Usage

### Install using pip:

```
pip install git+https://github.com/voun7/Subtitle_OCR.git
```

[OCR Models](https://1drv.ms/f/s!AjcgvUnda0Imi_UAUiJ__YWl6D8lZA) - Place downloaded models in `saved models` folder

``` python
from sub_ocr import SubtitleOCR

reader = SubtitleOCR("en")  # this needs to run only once to load the models into memory
result = reader.ocr("image_1.jpg")
```

The output will be in a list format, each item represents a bounding box, the text detected and confident level,
respectively.

```
[{'bbox': ((636, 69), (1284, 72), (1284, 156), (636, 138)), 'text': "Test image text", 'score': 0.8736287951469421},
{'bbox': ((552, 848), (1364, 864), (1366, 946), (552, 921)), 'text': 'another image text', 'score': 0.8997976183891296}]
```
