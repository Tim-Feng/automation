#!/usr/bin/env python3
import os
import cv2
import numpy as np
from typing import Optional
from pathlib import Path
import argparse
import sys

from logger import setup_logger

logger = setup_logger('smart_processor')

class SmartImageProcessor:
    def __init__(self, target_width: int = 1920, target_height: int = 3414, content_height: int = 2404):
        self.target_width = target_width
        self.target_height = target_height
        self.content_height = content_height
        
        # Calculate black frame height
        self.black_frame_height = (target_height - content_height) // 2

        # Initialize face detector (Haar Cascade)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

    def analyze_frame(self, frame, frame_pos: float = 0) -> dict:
        """
        針對「有人臉」的檢測與評分 (第一階段)。
        若抓不到臉，或分數不合格 => 之後可能走 fallback。
        """
        score = 0
        reasons = []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 這裡可調整參數
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=6,
            minSize=(80, 80)
        )

        if len(faces) == 1:
            # 只接收單臉
            x, y, w, h = faces[0]
            # 可以在這裡做臉部大小或邊緣檢查
            score += 30  # 單臉基礎分
        elif len(faces) > 1:
            reasons.append("Multiple faces => not using this frame")
            score = -999
        else:
            reasons.append("No face detected")
            score = -999

        # 簡單加點清晰度分數
        if score > 0:
            lap_val = cv2.Laplacian(gray, cv2.CV_64F).var()
            if lap_val > 200:
                score += 10
                reasons.append("Sharpness bonus")

        return {
            "score": score,
            "reasons": reasons,
            "faces": faces if (score > 0 and len(faces) == 1) else None,
            "frame": frame.copy() if score > 0 else None
        }

    def simple_quality_score(self, frame):
        """
        當「沒有人臉」時的 fallback 評分: 以清晰度 + 亮度評分，
        也可自行擴充對比度、色彩豐富度等。
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # (1) 清晰度: Laplacian
        lap_val = cv2.Laplacian(gray, cv2.CV_64F).var()

        # (2) 亮度適中度: 檢查 v_channel 的直方圖分布
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        v_channel = hsv[:, :, 2]
        hist = cv2.calcHist([v_channel], [0], None, [256], [0, 256])
        low_light = np.sum(hist[:64]) / np.sum(hist)   # 過暗比例
        high_light = np.sum(hist[192:]) / np.sum(hist) # 過亮比例

        # 亮度分
        brightness_score = 0
        if 0.05 < low_light < 0.4 and 0.05 < high_light < 0.4:
            brightness_score = 50

        total_score = lap_val + brightness_score
        return total_score

    def _crop_and_resize(self, image, faces=None):
        """
        你的裁切+貼黑邊邏輯：
         1) 等比縮放到高=2404
         2) 若有臉 => 水平居中
         3) 最終貼到1920x3414
        """
        final_w, final_h = 1920, 3414
        content_w, content_h = 1920, 2404
        black_top = (final_h - content_h) // 2

        orig_h, orig_w = image.shape[:2]
        scale = content_h / orig_h
        new_w = int(orig_w * scale)
        new_h = content_h
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        x_start = max(0, (new_w - content_w) // 2)

        if faces is not None and len(faces) > 0:
            # 找最大臉
            max_face = max(faces, key=lambda f: f[2] * f[3])
            fx, fy, fw, fh = max_face
            face_cx = fx + fw/2
            face_cx_scaled = face_cx * scale
            desired_cx = content_w / 2
            x_start = int(face_cx_scaled - desired_cx)
            if x_start < 0:
                x_start = 0
            elif x_start + content_w > new_w:
                x_start = new_w - content_w

        cropped = resized[:, x_start:x_start + content_w]

        final_img = np.zeros((final_h, final_w, 3), dtype=np.uint8)
        final_img[black_top:black_top + content_h, 0:content_w] = cropped
        return final_img

    def _detect_image_edges(self, gray_image):
        edges = cv2.Canny(gray_image, 100, 200)
        return np.sum(edges) / (edges.shape[0] * edges.shape[1])

    def process_image(self, input_path: str, output_path: str = None) -> Optional[str]:
        logger.info(f"Processing image: {input_path}")
        
        if not os.path.exists(input_path):
            logger.error(f"Input file not found: {input_path}")
            return None

        if output_path is None:
            base_path = os.path.splitext(input_path)[0]
            output_path = f"{base_path}_cover.jpg"

        image = cv2.imread(input_path)
        if image is None:
            logger.error(f"Unable to read image: {input_path}")
            return None

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edge_ratio = self._detect_image_edges(gray)
        if edge_ratio < 0.05:
            logger.warning("Image lacks sufficient detail")
            return None

        # 這裡若要也用嚴苛參數，可直接呼叫 analyze_frame(image)
        # 或用較鬆散的 detectMultiScale
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )

        processed_image = self._crop_and_resize(image, faces)
        if processed_image is not None:
            cv2.imwrite(output_path, processed_image)
            logger.info(f"Processed image saved: {output_path}")
            return output_path
        return None

    def pick_diverse_top_k(self, candidates, k=3, time_threshold=2.0):
        """
        時間間隔過近的只取最高分那張 => 保證多樣性
        """
        chosen = []
        for (score, frame, faces, frame_pos) in candidates:
            too_close = False
            for (_, _, _, chosen_pos) in chosen:
                if abs(frame_pos - chosen_pos) < time_threshold:
                    too_close = True
                    break
            if not too_close:
                chosen.append((score, frame, faces, frame_pos))
                if len(chosen) == k:
                    break
        return chosen

    def process_video(self, video_path: str, output_path: str = None):
        logger.info(f"Processing video: {video_path}")
        
        if not os.path.exists(video_path):
            logger.error("Video not found")
            return None

        if output_path is None:
            base_path = os.path.splitext(video_path)[0]
            output_path = f"{base_path}_cover.jpg"
        else:
            base_path = os.path.splitext(output_path)[0]

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error("Cannot open video")
            return None

        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            duration = total_frames / fps
            logger.info(f"Video info: {duration:.1f}s, FPS {fps}, total_frames={total_frames}")

            frame_interval = max(1, fps // 4)  # 4 frames/sec
            skip_end_sec = 3
            end_frame = total_frames - (skip_end_sec * fps)

            face_candidates = []
            current_frame = 0

            # --- (A) 第一輪：嘗試「有人臉」的候選 ---
            while current_frame < end_frame:
                cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
                ret, frame = cap.read()
                if not ret:
                    break

                if current_frame % frame_interval == 0:
                    frame_pos = current_frame / fps
                    analysis = self.analyze_frame(frame, frame_pos)
                    if analysis["score"] > 0 and analysis["faces"] is not None:
                        face_candidates.append((
                            analysis["score"],
                            frame.copy(),
                            analysis["faces"],
                            frame_pos
                        ))
                current_frame += frame_interval

            # 對「臉候選」排序 & 選擇 top3
            face_candidates.sort(key=lambda x: x[0], reverse=True)
            top_faces = self.pick_diverse_top_k(face_candidates, k=3, time_threshold=2.0)

            # --- (B) 若找不到臉 => fallback: 「畫面品質最高」 ---
            if not top_faces:
                logger.warning("No face found, fallback to quality-based selection...")

                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                current_frame = 0
                quality_candidates = []
                while current_frame < end_frame:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if current_frame % frame_interval == 0:
                        frame_pos = current_frame / fps
                        q_score = self.simple_quality_score(frame)
                        quality_candidates.append((q_score, frame.copy(), None, frame_pos))

                    current_frame += frame_interval

                quality_candidates.sort(key=lambda x: x[0], reverse=True)
                top_quality = self.pick_diverse_top_k(quality_candidates, k=3, time_threshold=2.0)

                if not top_quality:
                    logger.error("No suitable fallback frames found either.")
                    return None

                # (C) 產生檔案
                saved_paths = []
                for i, (score, qframe, _, fpos) in enumerate(top_quality, start=1):
                    processed = self._crop_and_resize(qframe, None)
                    out_path = f"{base_path}_noface_top{i}.jpg"
                    cv2.imwrite(out_path, processed)
                    logger.info(f"Fallback saved: {out_path} (score={score:.1f}, time={fpos:.1f}s)")
                    saved_paths.append(out_path)

                return saved_paths[0]  # 回傳第一張

            else:
                # (C) 對「有人臉」的結果進行裁切 & 輸出
                saved_paths = []
                for i, (score, frame_with_face, faces, fpos) in enumerate(top_faces, start=1):
                    final_img = self._crop_and_resize(frame_with_face, faces)
                    out_path = f"{base_path}_top{i}.jpg"
                    cv2.imwrite(out_path, final_img)
                    logger.info(f"Face cover saved: {out_path} (score={score:.1f}, time={fpos:.1f}s)")
                    saved_paths.append(out_path)

                return saved_paths[0]

        finally:
            cap.release()
        return None

def main():
    parser = argparse.ArgumentParser(description='Smart Image/Video Cover Processor')
    parser.add_argument('input_path', help='Path to input image or video')
    parser.add_argument('-o', '--output', help='Path to save processed cover', default=None)
    args = parser.parse_args()

    processor = SmartImageProcessor()
    try:
        input_ext = os.path.splitext(args.input_path)[1].lower()
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}

        if input_ext in video_extensions:
            result = processor.process_video(args.input_path, args.output)
        elif input_ext in image_extensions:
            result = processor.process_image(args.input_path, args.output)
        else:
            logger.error(f"Unsupported file type: {input_ext}")
            return None

        if result:
            print(f"{result}")
        else:
            print("Processing failed")

    except Exception as e:
        logger.error(f"Processing error: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()