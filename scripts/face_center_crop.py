import cv2
import numpy as np
import os
from typing import Tuple, Optional

class SmartImageProcessor:
    def __init__(self, target_width: int = 1920, target_height: int = 3414):
        self.target_width = target_width
        self.target_height = target_height
        self.aspect_ratio = target_height / target_width
        
        # 輸入圖片的預期尺寸
        self.expected_width = 2560
        self.expected_height = 1600
        
        # 裁切後的高度（移除播放器UI）
        self.crop_height = 1280
        
        # 初始化人臉偵測器
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

    def crop_screenshot(self, image: np.ndarray) -> Optional[np.ndarray]:
        """裁切掉播放器UI"""
        height, width = image.shape[:2]
        print(f"輸入圖片尺寸: {width}x{height}")
        
        if width != self.expected_width or height != self.expected_height:
            print(f"警告：輸入圖片尺寸不符合預期 ({self.expected_width}x{self.expected_height})")
            return None
            
        # 裁切掉底部的播放器UI
        cropped = image[0:self.crop_height, 0:width]
        print(f"移除UI後尺寸: {cropped.shape[1]}x{cropped.shape[0]}")
        return cropped

    def get_face_center(self, image: np.ndarray) -> Tuple[int, int]:
        """取得人臉中心點，如果沒有偵測到人臉則返回圖片中心"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        if len(faces) == 0:
            print("警告：沒有偵測到人臉，使用圖片中心點")
            return (image.shape[1] // 2, image.shape[0] // 2)

        # 取得最大的人臉（通常是最接近鏡頭的）
        max_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = max_face
        center_x = x + w // 2
        center_y = y + h // 2
        print(f"偵測到人臉中心點: ({center_x}, {center_y})")
        return (center_x, center_y)

    def process_image(self, image_path: str, output_path: str) -> bool:
        """處理圖片主函數"""
        print(f"\n開始處理圖片: {image_path}")
        
        if not os.path.exists(image_path):
            print(f"錯誤：找不到輸入檔案: {image_path}")
            return False
        
        # 讀取圖片
        image = cv2.imread(image_path)
        if image is None:
            print(f"錯誤：無法讀取圖片: {image_path}")
            return False

        # 裁切掉播放器UI
        image = self.crop_screenshot(image)
        if image is None:
            return False
        
        # 獲取人臉中心點
        face_center_x, face_center_y = self.get_face_center(image)
        
        # 計算裁切區域
        current_height, current_width = image.shape[:2]
        target_aspect = self.target_height / self.target_width
        
        # 以人臉為中心進行裁切
        if current_width / current_height > 1/target_aspect:
            # 圖片太寬，需要垂直裁切
            new_width = int(current_height * (1/target_aspect))
            x1 = max(0, min(face_center_x - new_width//2, current_width - new_width))
            cropped = image[:, x1:x1+new_width]
        else:
            # 圖片太高，需要水平裁切
            new_height = int(current_width * target_aspect)
            y1 = max(0, min(face_center_y - new_height//2, current_height - new_height))
            cropped = image[y1:y1+new_height, :]

        # 調整到最終尺寸
        resized = cv2.resize(cropped, (self.target_width, self.target_height))
        
        # 儲存結果
        cv2.imwrite(output_path, resized)
        print(f"處理完成，已儲存至: {output_path}")
        return True


def main():
    # 使用範例
    processor = SmartImageProcessor(1920, 3414)
    
    # 設定輸入和輸出檔案名稱
    input_file = 'input.jpeg'
    output_file = 'output.jpeg'
    
    # 處理圖片
    result = processor.process_image(input_file, output_file)
    
    if result:
        print("\n圖片處理成功完成！")
        print(f"請檢查輸出檔案: {output_file}")
    else:
        print("\n圖片處理失敗！")


if __name__ == "__main__":
    main()