import logging
import os
from pathlib import Path

import numpy as np
import torch

from sub_ocr.models.detection import DB, DBPostProcess
from sub_ocr.models.recognition import CRNN, LabelPostProcess
from sub_ocr.utils import Types, read_image, read_chars, resize_norm_img, pascal_voc_bb, flatten_iter

logger = logging.getLogger(__name__)


class SubtitleOCR:
    supported_languages = [Types.english, ]

    def __init__(self, lang: Types.Language | str = Types.english, model_dir: Path = Path("saved models")) -> None:
        assert lang in self.supported_languages, "Requested language not available!"
        self.models_dir, self.device = model_dir, "cuda" if torch.cuda.is_available() else "cpu"
        self.det_model, self.det_post_process, self.det_img_h, self.det_img_w = self.init_model(lang)
        self.rec_model, self.rec_post_process, self.rec_img_h, self.rec_img_w = self.init_model(lang, Types.rec)

    def init_model(self, lang: Types.Language, model_type: Types.ModelType = Types.det) -> tuple:
        """
        Setup model and post processor.
        """
        assert self.models_dir.exists(), "Model save location not found!"
        if model_type is Types.det:
            backbone, image_h, image_w = "deformable_resnet50", 640, 640
            model_params = {"backbone_name": backbone, "pretrained": False}
            model, file = DB(**model_params), next(self.models_dir.glob(f"{lang} {Types.db} {backbone} *.pt"))
            post_processor = DBPostProcess()
        else:
            alphabet, backbone, image_h, image_w = read_chars(lang), "", 32, None
            model_params = {"image_height": image_h, "num_class": len(alphabet) + 1}
            model, file = CRNN(**model_params), next(self.models_dir.glob(f"{lang} {Types.crnn} {backbone} *.pt"))
            post_processor = LabelPostProcess(alphabet)

        logger.debug(f"Device: {self.device}, Model Params: {model_params}, File: {file}")
        model.load_state_dict(torch.load(file, map_location=self.device))
        model.to(self.device).eval()
        return model, post_processor, image_h, image_w

    @staticmethod
    def sort_merge_bboxes(bboxes: np.ndarray, threshold: int = 10) -> list:
        """
        Sort and merge bboxes that are very close and on the same horizontal line to create larger bboxes.
        The y-coordinates is used because bounding boxes that are aligned horizontally will have similar y-coordinates.
        e.g, Single word bboxes that are close to each other would merge together to form a bbox containing a sentence.
        """

        def merge(bboxes_: np.ndarray) -> tuple:
            n_x1, n_y1 = np.min(bboxes_[:, 0], axis=0)
            n_x2, n_y2 = np.max(bboxes_[:, 1], axis=0)
            n_x3, n_y3 = np.max(bboxes_[:, 2], axis=0)
            n_x4, n_y4 = np.min(bboxes_[:, 3], axis=0)
            return (n_x1, n_y1), (n_x2, n_y2), (n_x3, n_y3), (n_x4, n_y4)

        # Calculate the average y-coordinate for each bbox
        avg_y = np.mean(bboxes[:, :, 1], axis=1)
        # Sort the bounding boxes by their average y-coordinate
        sorted_indices = np.argsort(avg_y)
        sorted_bboxes, sorted_avg_y = bboxes[sorted_indices], avg_y[sorted_indices]
        # Find the differences between consecutive average y-coordinates
        diff_y = np.diff(sorted_avg_y, prepend=sorted_avg_y[0])
        # Identify groups based on the threshold
        group_labels = np.cumsum(diff_y > threshold)
        # Use advanced indexing to group bounding boxes
        groups = [sorted_bboxes[group_labels == i] for i in np.unique(group_labels)]
        return [{"bbox": merge(bbs)} for bbs in groups]

    def text_detector(self, image: np.ndarray, image_height: int, image_width: int) -> list:
        image = resize_norm_img(image, self.det_img_h, self.det_img_w, False)[0]
        image = torch.from_numpy(image).to(self.device)
        prediction = self.det_model(image.unsqueeze(0))
        batch = {"shape": [(image_height, image_width)]}
        bboxes, scores = self.det_post_process(batch, prediction)
        bboxes = bboxes[0][scores[0] > 0]  # Remove bbox indexes with a score of zero.
        labels = self.sort_merge_bboxes(bboxes) if bboxes.size else []
        # labels = [{"bbox": bb.tolist()} for bb in bboxes]  # to be removed later
        return labels

    def text_recognizer(self, image: np.ndarray, labels: list) -> list:
        def recognizer(img: np.ndarray) -> tuple:
            img = resize_norm_img(img, self.rec_img_h, self.rec_img_w or img.shape[1],
                                  True if self.rec_img_w else img.shape[0] < self.rec_img_h)[0]
            img = torch.from_numpy(img).to(self.device)
            prediction = self.rec_model(img.unsqueeze(0))
            return self.rec_post_process(prediction)

        if labels:
            for label in labels:
                x_min, y_min, x_max, y_max = pascal_voc_bb(tuple(flatten_iter(label["bbox"])))
                cropped_image = image[y_min:y_max, x_min:x_max]  # crop image with bbox
                label["text"], label["score"] = recognizer(cropped_image)
        else:
            labels = [{"text": text, "score": score} for text, score in [recognizer(image)]]
        return labels

    @torch.no_grad()
    def ocr(self, image_path: str, det: bool = True, rec: bool = True) -> list:
        image, image_height, image_width = read_image(image_path)
        labels = self.text_detector(image, image_height, image_width) if det else []
        labels = self.text_recognizer(image, labels) if rec else labels
        return labels


def test_ocr() -> None:
    username = os.getlogin()
    models_dir = Path(rf"C:\Users\{username}\OneDrive\Backups\Subtitle OCR Models")
    test_image_files = Path(rf"C:\Users\{username}\OneDrive\Public\test images")
    test_sub_ocr = SubtitleOCR(model_dir=models_dir)
    for test_image in test_image_files.iterdir():
        test_outputs = test_sub_ocr.ocr(str(test_image))
        logger.info(test_image)
        for test_output in test_outputs:
            logger.info(test_output)
        logger.info("")
        visualize_data(str(test_image), test_outputs, False, True)


if __name__ == '__main__':
    from utilities.logger_setup import setup_logging
    from utilities.visualize import visualize_data

    setup_logging()
    logger.debug("Logging Started")
    test_ocr()
    logger.debug("Logging Ended\n\n")
