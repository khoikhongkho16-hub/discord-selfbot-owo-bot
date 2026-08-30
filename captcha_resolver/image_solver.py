import os
import io
import numpy as np
from PIL import Image, UnidentifiedImageError
import onnxruntime
from typing import Optional, Dict, Any, Union
import aiohttp
import asyncio


class ImageSolver:
    
    def __init__(self, model_path: str = 'best.onnx', bot=None):
        self.model_path = model_path
        self.bot = bot
        self.canvas_size = 384
        self.alphabet = "abcdefghijklmnopqrstuvwxyz"
        self.min_score = 0.3
        self.pad = (114, 114, 114)
        
        self._engine = None
        self._feed = None
        self._loaded = False
        self._load_model()
    
    def _log(self, level: str, msg: str):
        return
    
    def _load_model(self):
        try:
            if not os.path.exists(self.model_path):
                return
            
            self._engine = onnxruntime.InferenceSession(
                self.model_path,
                providers=["CPUExecutionProvider"]
            )
            self._feed = self._engine.get_inputs()[0].name
            self._loaded = True
        except Exception as e:
            self._loaded = False
    
    def _fit_square(self, frame: np.ndarray) -> np.ndarray:
        pic = Image.fromarray(frame)
        width, height = pic.size
        ratio = min(self.canvas_size / width, self.canvas_size / height)
        target = (max(1, int(width * ratio)), max(1, int(height * ratio)))
        shrunk = pic.resize(target, Image.BILINEAR)
        
        canvas = Image.new("RGB", (self.canvas_size, self.canvas_size), self.pad)
        offset = ((self.canvas_size - target[0]) // 2, 
                  (self.canvas_size - target[1]) // 2)
        canvas.paste(shrunk, offset)
        return np.asarray(canvas)
    
    def _to_tensor(self, frame: np.ndarray) -> np.ndarray:
        tensor = self._fit_square(frame).astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))
        return tensor[np.newaxis, ...]
    
    def _load_image_safe(self, image_data: bytes) -> Optional[Image.Image]:
        try:
            img = Image.open(io.BytesIO(image_data))
            return img
        except UnidentifiedImageError:
            import imghdr
            img_type = imghdr.what(None, h=image_data)
            
            if img_type:
                try:
                    img = Image.open(io.BytesIO(image_data))
                    return img
                except:
                    pass
            
            try:
                import cv2
                import numpy as np
                nparr = np.frombuffer(image_data, np.uint8)
                img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img_cv is not None:
                    img_cv_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(img_cv_rgb)
                    return img
            except ImportError:
                pass
            except Exception as e:
                pass
            
            return None
        except Exception as e:
            return None
    
    def solve(self, image_data: Union[bytes, str, Image.Image], expected_length: int = 6) -> Optional[str]:
        try:
            if not self._loaded:
                return None
            
            img = None
            
            if isinstance(image_data, bytes):
                img = self._load_image_safe(image_data)
                if img is None:
                    return None
                    
            elif isinstance(image_data, str) and os.path.exists(image_data):
                try:
                    with open(image_data, 'rb') as f:
                        data = f.read()
                    img = self._load_image_safe(data)
                    if img is None:
                        return None
                except Exception as e:
                    return None
                    
            elif isinstance(image_data, Image.Image):
                img = image_data
            else:
                return None
            
            if img.mode != 'RGB':
                img = img.convert("RGB")
            
            frame = np.asarray(img)
            
            tensor = self._to_tensor(frame)
            raw = self._engine.run(None, {self._feed: tensor})[0][0]
            
            found = []
            for row in raw:
                ax, ay, bx, by, score, label = row
                if score < self.min_score:
                    continue
                found.append((float((ax + bx) / 2), float(score), self.alphabet[int(label)]))
            
            if not found:
                return None
            
            if expected_length and len(found) > expected_length:
                found.sort(key=lambda item: item[1], reverse=True)
                found = found[:expected_length]
            
            found.sort(key=lambda item: item[0])
            result = "".join(item[2] for item in found)
            
            return result if len(result) >= 3 else None
            
        except Exception as e:
            return None
    
    async def solve_from_url(self, image_url: str, expected_length: int = 6) -> Optional[str]:
        try:
            if not self._loaded:
                return None
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                async with session.get(image_url, headers=headers, timeout=15) as resp:
                    if resp.status != 200:
                        return None
                    
                    image_data = await resp.read()
                    
                    if not image_data or len(image_data) < 100:
                        return None
            
            result = self.solve(image_data, expected_length)
            return result
            
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            return None
    
    def is_available(self) -> bool:
        return self._loaded