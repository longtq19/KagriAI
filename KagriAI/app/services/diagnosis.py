import os
import base64
import numpy as np
import cv2
from ultralytics import YOLO
from typing import List, Dict, Any

class DiagnosisService:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.models_dir = os.path.join(self.base_path, "models")
        self.images_dir = os.path.join(self.base_path, "data", "images")
        
        self.durian_model_path = os.path.join(self.models_dir, "durianDiseasesModel.pt")
        self.coffee_model_path = os.path.join(self.models_dir, "coffeeDiseasesModel.pt")
        
        self.durian_model = None
        self.coffee_model = None
        
        self.load_models()
        
        self.durian_map = {
            "anthracnose_disease": "Thán thư",
            "canker_disease": "loét thân",
            "fruit_rot": "Thối trái",
            "mealybug_infestation": "Rệp sáp",
            "pink_disease": "Nấm hồng",
            "sooty_mold": "Bồ hóng",
            "stem_blight": "Cháy lá chết ngọn",
            "stem_cracking_ gummosis": "Xì mủ thân",
            "thrips_disease": "Bọ trĩ",
            "yellow_leaf": "Vàng lá"
        }
        
        self.coffee_map = {
            "Healthy": "Khỏe mạnh",
            "Leaf rust": "Gỉ sắt",
            "Miner": "Sâu vẽ bùa (sâu đục lá)",
            "Phoma": "Đốm nấm Phoma"
        }

    def load_models(self):
        try:
            if os.path.exists(self.durian_model_path):
                self.durian_model = YOLO(self.durian_model_path)
                print(f"Durian model loaded from {self.durian_model_path}")
            else:
                print(f"Durian model not found at {self.durian_model_path}")

            if os.path.exists(self.coffee_model_path):
                self.coffee_model = YOLO(self.coffee_model_path)
                print(f"Coffee model loaded from {self.coffee_model_path}")
            else:
                print(f"Coffee model not found at {self.coffee_model_path}")
        except Exception as e:
            print(f"Error loading models: {e}")

    def _get_example_images(self, disease_class: str, plant_type: str) -> List[str]:
        """
        Returns a list of 2 image paths (relative to static mount) for the given disease.
        """
        subdir = "durianDiseases" if plant_type == "durian" else "coffeeDiseases"
        disease_dir = os.path.join(self.images_dir, subdir, disease_class)
        
        images = []
        if os.path.exists(disease_dir):
            files = os.listdir(disease_dir)
            # Filter for images
            valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')
            image_files = [f for f in files if f.lower().endswith(valid_extensions)]
            
            # Take up to 2
            for img_file in image_files[:2]:
                # Construct URL path. Assuming we mount data/images at /images
                # path should be /images/{subdir}/{disease_class}/{img_file}
                # We need to URL encode parts if necessary, but simple concatenation usually works for standard filenames
                # However, "stem_cracking_ gummosis" has a space.
                from urllib.parse import quote
                
                # We want the path to be used in frontend src.
                # If backend mounts 'data/images' to '/images'
                encoded_disease = quote(disease_class)
                encoded_file = quote(img_file)
                url_path = f"/images/{subdir}/{encoded_disease}/{encoded_file}"
                images.append(url_path)
                
        return images

    def predict(self, image_base64: str, plant_type: str) -> Dict[str, Any]:
        if plant_type == "durian":
            model = self.durian_model
            mapping = self.durian_map
        elif plant_type == "coffee":
            model = self.coffee_model
            mapping = self.coffee_map
        else:
            return {"error": "Invalid plant type"}

        if not model:
            return {"error": "Model not loaded"}

        try:
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            
            image_data = base64.b64decode(image_base64)
            np_arr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if img is None:
                return {"error": "Invalid image"}

            results = model(img)
            
            output = []
            
            if results and len(results) > 0:
                result = results[0]
                
                # Check if it's a classification model
                if hasattr(result, 'probs') and result.probs is not None:
                    # Get top 3
                    # top5 attribute usually exists, but let's be safe
                    # result.probs.top5 is a list of indices
                    # result.probs.top5conf is a list of confidences (tensors)
                    
                    probs = result.probs
                    
                    # We need to get indices and scores manually if topk helpers aren't exactly what we want
                    # But ultralytics usually provides .top5
                    
                    top_indices = probs.top5 # List[int]
                    top_conf = probs.top5conf # Tensor
                    
                    limit = min(3, len(top_indices))
                    
                    for i in range(limit):
                        idx = top_indices[i]
                        score = float(top_conf[i])
                        class_name = result.names[idx]
                        
                        vietnamese_name = mapping.get(class_name, class_name)
                        example_images = self._get_example_images(class_name, plant_type)
                        
                        output.append({
                            "name": vietnamese_name,
                            "original_name": class_name,
                            "probability": round(score * 100, 2),
                            "images": example_images
                        })
                else:
                    # Fallback for detection models if used as classification
                    # Not expected based on requirements, but handling just in case
                    return {"error": "Model output format not supported (expected classification)"}

            return {"predictions": output}

        except Exception as e:
            print(f"Error in prediction: {e}")
            return {"error": str(e)}

diagnosis_service = DiagnosisService()
