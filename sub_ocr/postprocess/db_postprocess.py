"""
This code is referred from:
https://github.com/WenmuZhou/DBNet.pytorch/blob/master/post_processing/seg_detector_representer.py
"""

import cv2 as cv
import numpy as np
import pyclipper
from shapely.geometry import Polygon


class DBPostProcess:
    """
    The post process for Differentiable Binarization (DB).
    """

    def __init__(self, thresh=0.3, box_thresh=0.7, max_candidates=1000, unclip_ratio=2):
        self.thresh = thresh
        self.box_thresh = box_thresh
        self.max_candidates = max_candidates
        self.un_clip_ratio = unclip_ratio
        self.min_size = 3

    def __call__(self, batch, prediction, is_output_polygon=False):
        """
        batch: image, polygons
        or
        batch: a dict produced by dataloaders.
            image: tensor of shape (N, C, H, W).
            bbox: tensor of shape (N, K, 4, 2), the polygons of objective regions.
            shape: the original shape of images.
            image_path: the original filenames of images.
        prediction:
            binary: text region segmentation map, with shape (N, H, W)
            thresh: [if exists] thresh hold prediction with shape (N, H, W)
            thresh_binary: [if exists] binarized with threshold, (N, H, W)
        """
        prediction = prediction[:, 0, :, :]
        segmentation = self.binarize(prediction)
        boxes_batch = []
        scores_batch = []
        for batch_index in range(prediction.size(0)):
            height, width = batch['shape'][batch_index]
            if is_output_polygon:
                boxes, scores = self.polygons_from_bitmap(prediction[batch_index], segmentation[batch_index], width,
                                                          height)
            else:
                boxes, scores = self.boxes_from_bitmap(prediction[batch_index], segmentation[batch_index], width,
                                                       height)
            boxes_batch.append(boxes)
            scores_batch.append(scores)
        return boxes_batch, scores_batch

    def binarize(self, prediction):
        return prediction > self.thresh

    def polygons_from_bitmap(self, prediction, _bitmap, dest_width, dest_height):
        """
        _bitmap: single map with shape (H, W), whose values are binarized as {0, 1}
        """
        assert len(_bitmap.shape) == 2
        bitmap = _bitmap.cpu().numpy()  # The first channel
        prediction = prediction.cpu().detach().numpy()
        height, width = bitmap.shape
        boxes = []
        scores = []

        contours, _ = cv.findContours((bitmap * 255).astype(np.uint8), cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE)

        for contour in contours[:self.max_candidates]:
            epsilon = 0.002 * cv.arcLength(contour, True)
            approx = cv.approxPolyDP(contour, epsilon, True)
            points = approx.reshape((-1, 2))
            if points.shape[0] < 4:
                continue

            score = self.box_score_fast(prediction, contour.squeeze(1))
            if self.box_thresh > score:
                continue

            if points.shape[0] > 2:
                box = self.un_clip(points, self.un_clip_ratio)
                if len(box) > 1:
                    continue
            else:
                continue
            box = box.reshape(-1, 2)

            _, sside = self.get_mini_boxes(box.reshape((-1, 1, 2)))
            if sside < self.min_size + 2:
                continue

            if not isinstance(dest_width, int):
                dest_width = dest_width.item()
                dest_height = dest_height.item()

            box[:, 0] = np.clip(np.round(box[:, 0] / width * dest_width), 0, dest_width)
            box[:, 1] = np.clip(np.round(box[:, 1] / height * dest_height), 0, dest_height)
            boxes.append(box)
            scores.append(score)
        return boxes, scores

    def boxes_from_bitmap(self, prediction, _bitmap, dest_width, dest_height):
        """
        _bitmap: single map with shape (H, W), whose values are binarized as {0, 1}
        """
        assert len(_bitmap.shape) == 2
        bitmap = _bitmap.cpu().numpy()  # The first channel
        prediction = prediction.cpu().detach().numpy()
        height, width = bitmap.shape
        contours, _ = cv.findContours((bitmap * 255).astype(np.uint8), cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE)
        num_contours = min(len(contours), self.max_candidates)
        boxes = np.zeros((num_contours, 4, 2), dtype=np.int16)
        scores = np.zeros((num_contours,), dtype=np.float32)

        for index in range(num_contours):
            contour = contours[index].squeeze(1)
            points, sside = self.get_mini_boxes(contour)
            if sside < self.min_size:
                continue
            points = np.array(points)
            score = self.box_score_fast(prediction, contour)
            if self.box_thresh > score:
                continue

            box = self.un_clip(points, self.un_clip_ratio).reshape(-1, 1, 2)
            box, sside = self.get_mini_boxes(box)
            if sside < self.min_size + 2:
                continue
            box = np.array(box)
            if not isinstance(dest_width, int):
                dest_width = dest_width.item()
                dest_height = dest_height.item()

            box[:, 0] = np.clip(np.round(box[:, 0] / width * dest_width), 0, dest_width)
            box[:, 1] = np.clip(np.round(box[:, 1] / height * dest_height), 0, dest_height)
            boxes[index, :, :] = box.astype(np.int16)
            scores[index] = score
        return boxes, scores

    @staticmethod
    def un_clip(box, un_clip_ratio):
        poly = Polygon(box)
        distance = poly.area * un_clip_ratio / poly.length
        offset = pyclipper.PyclipperOffset()
        offset.AddPath(box, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        expanded = np.array(offset.Execute(distance))
        return expanded

    @staticmethod
    def get_mini_boxes(contour):
        bounding_box = cv.minAreaRect(contour)
        points = sorted(list(cv.boxPoints(bounding_box)), key=lambda x: x[0])

        index_1, index_2, index_3, index_4 = 0, 1, 2, 3
        if points[1][1] > points[0][1]:
            index_1 = 0
            index_4 = 1
        else:
            index_1 = 1
            index_4 = 0
        if points[3][1] > points[2][1]:
            index_2 = 2
            index_3 = 3
        else:
            index_2 = 3
            index_3 = 2

        box = [points[index_1], points[index_2], points[index_3], points[index_4]]
        return box, min(bounding_box[1])

    @staticmethod
    def box_score_fast(bitmap, _box):
        h, w = bitmap.shape[:2]
        box = _box.copy()
        x_min = np.clip(np.floor(box[:, 0].min()).astype(np.int32), 0, w - 1)
        x_max = np.clip(np.ceil(box[:, 0].max()).astype(np.int32), 0, w - 1)
        y_min = np.clip(np.floor(box[:, 1].min()).astype(np.int32), 0, h - 1)
        y_max = np.clip(np.ceil(box[:, 1].max()).astype(np.int32), 0, h - 1)

        mask = np.zeros((y_max - y_min + 1, x_max - x_min + 1), dtype=np.uint8)
        box[:, 0] = box[:, 0] - x_min
        box[:, 1] = box[:, 1] - y_min
        cv.fillPoly(mask, box.reshape(1, -1, 2).astype(np.int32), 1)
        return cv.mean(bitmap[y_min:y_max + 1, x_min:x_max + 1], mask)[0]
