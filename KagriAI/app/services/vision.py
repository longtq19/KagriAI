import base64
import numpy as np
import cv2
from ultralytics import YOLO
import os

class VisionEngine:
    def __init__(self):
        # Load YOLO model
        model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models", "best.pt")
        # Ensure path is correct, might be cleaner to hardcode or use config if path structure changes
        # Given structure: app/services/vision.py -> app/services -> app -> KagriAI -> models/best.pt is in KagriAI/models?
        # LS showed: KagriAI/models/best.pt
        # So __file__ is .../KagriAI/app/services/vision.py
        # dirname -> .../KagriAI/app/services
        # dirname -> .../KagriAI/app
        # dirname -> .../KagriAI
        # join "models", "best.pt" -> .../KagriAI/models/best.pt
        
        try:
            self.model = YOLO(model_path)
            print(f"YOLO model loaded from {model_path}")
        except Exception as e:
            print(f"Error loading YOLO model: {e}")
            self.model = None

    def predict(self, image_base64: str) -> str:
        """
        Analyzes image (base64) and returns diagnosis class name.
        """
        if not self.model:
            return "Model not loaded"

        try:
            # Decode base64
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            
            image_data = base64.b64decode(image_base64)
            np_arr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if img is None:
                return "Invalid image"

            # Run inference
            results = self.model(img)
            
            # Get result
            # Assuming single object or taking the one with highest confidence
            if results and len(results) > 0:
                result = results[0]
                if hasattr(result, 'names') and hasattr(result.probs, 'top1'):
                     # For classification model
                     if result.probs:
                        top1 = result.probs.top1
                        name = result.names[top1]
                        return name
                
                # For detection model (boxes)
                if hasattr(result, 'boxes'):
                    boxes = result.boxes
                    if len(boxes) > 0:
                        # Get the class with highest confidence
                        # boxes.conf is a tensor, boxes.cls is a tensor
                        # We can just take the first one or find max conf
                        # Assuming results are sorted or we take first
                        cls_id = int(boxes.cls[0].item())
                        name = result.names[cls_id]
                        return name
            
            return "Không phát hiện bệnh"
        except Exception as e:
            print(f"Error in prediction: {e}")
            return "Lỗi chẩn đoán"

vision_engine = VisionEngine()

