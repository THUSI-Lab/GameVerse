"""
弹弓位置检测器

使用模板匹配自动识别游戏中弹弓上小鸟的位置
"""

import os
import logging
import cv2
import numpy as np
from typing import Optional, Tuple, Dict
from PIL import Image

logger = logging.getLogger(__name__)


class SlingshotDetector:
    """
    弹弓位置检测器
    
    使用 OpenCV 模板匹配算法自动识别游戏截图中弹弓上小鸟的位置。
    优先检测 bird_on_slingshot (更精确的拉弓起点)，失败时回退到 slingshot。
    """
    
    def __init__(self, 
                 bird_template_path: Optional[str] = None,
                 slingshot_template_path: Optional[str] = None):
        """
        初始化弹弓检测器
        
        Args:
            bird_template_path: 弹弓上小鸟模板图片路径
            slingshot_template_path: 弹弓模板图片路径
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        images_dir = os.path.join(os.path.dirname(current_dir), "images")
        
        # 设置默认模板路径
        if bird_template_path is None:
            bird_template_path = os.path.join(images_dir, "bird_on_slingshot.png")
        if slingshot_template_path is None:
            slingshot_template_path = os.path.join(images_dir, "slingshot.png")
        
        self.bird_template_path = bird_template_path
        self.slingshot_template_path = slingshot_template_path
        
        # 模板存储
        self.templates = {}
        
        # 加载模板
        self._load_templates()
        
    def _load_templates(self):
        """加载所有模板图片"""
        # 加载 bird_on_slingshot 模板
        if os.path.exists(self.bird_template_path):
            bird_template = cv2.imread(self.bird_template_path)
            if bird_template is not None:
                self.templates['bird'] = {
                    'color': bird_template,
                    'gray': cv2.cvtColor(bird_template, cv2.COLOR_BGR2GRAY),
                    'path': self.bird_template_path
                }
                logger.info(f"Loaded bird_on_slingshot template from {self.bird_template_path}")
                logger.info(f"Bird template size: {bird_template.shape[1]}x{bird_template.shape[0]}")
            else:
                logger.warning(f"Failed to load bird template: {self.bird_template_path}")
        else:
            logger.warning(f"Bird template not found: {self.bird_template_path}")
        
        # 加载 slingshot 模板 (备用)
        if os.path.exists(self.slingshot_template_path):
            slingshot_template = cv2.imread(self.slingshot_template_path)
            if slingshot_template is not None:
                self.templates['slingshot'] = {
                    'color': slingshot_template,
                    'gray': cv2.cvtColor(slingshot_template, cv2.COLOR_BGR2GRAY),
                    'path': self.slingshot_template_path
                }
                logger.info(f"Loaded slingshot template from {self.slingshot_template_path}")
                logger.info(f"Slingshot template size: {slingshot_template.shape[1]}x{slingshot_template.shape[0]}")
            else:
                logger.warning(f"Failed to load slingshot template: {self.slingshot_template_path}")
        else:
            logger.warning(f"Slingshot template not found: {self.slingshot_template_path}")
        
        if not self.templates:
            raise FileNotFoundError("No templates loaded successfully")
    
    def _match_template(self, img_gray: np.ndarray, template_gray: np.ndarray,
                       threshold: float,
                       scale_range: Tuple[float, float],
                       scale_steps: int) -> Optional[Dict]:
        """
        在图像中匹配模板
        
        Args:
            img_gray: 灰度图像
            template_gray: 灰度模板
            threshold: 匹配阈值
            scale_range: 缩放范围
            scale_steps: 缩放步数
            
        Returns:
            匹配结果字典，包含 score, location, scale，如果未找到返回 None
        """
        img_height, img_width = img_gray.shape
        
        best_match = None
        best_score = threshold
        best_scale = 1.0
        
        # 多尺度模板匹配
        scales = np.linspace(scale_range[0], scale_range[1], scale_steps)
        
        for scale in scales:
            # 缩放模板
            template_width = int(template_gray.shape[1] * scale)
            template_height = int(template_gray.shape[0] * scale)
            
            if template_width > img_width or template_height > img_height:
                continue
            
            scaled_template = cv2.resize(
                template_gray, 
                (template_width, template_height),
                interpolation=cv2.INTER_AREA
            )
            
            # 模板匹配
            result = cv2.matchTemplate(
                img_gray, 
                scaled_template, 
                cv2.TM_CCOEFF_NORMED
            )
            
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # 如果找到更好的匹配
            if max_val > best_score:
                best_score = max_val
                best_match = max_loc
                best_scale = scale
                logger.debug(f"Better match found: scale={scale:.2f}, score={max_val:.3f}, loc={max_loc}")
        
        if best_match is not None:
            return {
                'score': best_score,
                'location': best_match,
                'scale': best_scale,
                'template_size': (
                    int(template_gray.shape[1] * best_scale),
                    int(template_gray.shape[0] * best_scale)
                )
            }
        return None
    
    def detect(self, image: Image.Image, 
               threshold: float = 0.7,
               scale_range: Tuple[float, float] = (0.5, 1.5),
               scale_steps: int = 20,
               prefer_bird: bool = True) -> Optional[Tuple[float, float, str]]:
        """
        在游戏截图中检测弹弓上小鸟的位置
        
        优先级:
        1. 优先尝试检测 bird_on_slingshot (更精确的拉弓起点)
        2. 如果失败，回退到检测 slingshot (备用方案)
        
        Args:
            image: PIL Image 游戏截图
            threshold: 匹配阈值 (0-1), 越高越严格
            scale_range: 缩放范围 (min_scale, max_scale)
            scale_steps: 缩放步数
            prefer_bird: 是否优先使用 bird 模板
            
        Returns:
            (相对x坐标, 相对y坐标, 弹弓高度(像素), 检测类型)
            - 相对坐标范围 0-1
            - 弹弓高度: 检测到的弹弓模板的实际像素高度
            - 检测类型: 'bird' 或 'slingshot'
            - 如果未找到返回 None
        """
        try:
            # 将 PIL Image 转换为 OpenCV 格式
            img_np = np.array(image)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            
            img_height, img_width = img_gray.shape
            
            # 定义检测顺序
            if prefer_bird and 'bird' in self.templates:
                detection_order = ['bird', 'slingshot']
            else:
                detection_order = ['slingshot', 'bird']
            
            # 按优先级尝试检测
            for template_type in detection_order:
                if template_type not in self.templates:
                    continue
                
                logger.info(f"Trying detection with {template_type} template...")
                template_gray = self.templates[template_type]['gray']
                
                match_result = self._match_template(
                    img_gray, template_gray, threshold, scale_range, scale_steps
                )
                
                if match_result is not None:
                    # 计算中心位置
                    template_width, template_height = match_result['template_size']
                    center_x = match_result['location'][0] + template_width // 2
                    center_y = match_result['location'][1] + template_height // 2
                    
                    # 转换为相对坐标
                    rel_x = center_x / img_width
                    rel_y = center_y / img_height
                    
                    logger.info(f"{template_type.capitalize()} detected at ({center_x}, {center_y}) = ({rel_x:.3f}, {rel_y:.3f})")
                    logger.info(f"Match score: {match_result['score']:.3f}, scale: {match_result['scale']:.2f}")
                    logger.info(f"Template height: {template_height} pixels")
                    
                    return (rel_x, rel_y, template_height, template_type)
            
            logger.warning(f"No template matched (threshold: {threshold})")
            return None
                
        except Exception as e:
            logger.error(f"Error detecting slingshot: {e}")
            return None
    
    def detect_with_visualization(self, image: Image.Image, 
                                  output_path: Optional[str] = None,
                                  **kwargs) -> Optional[Tuple[float, float, str]]:
        """
        检测弹弓并可视化结果
        
        Args:
            image: PIL Image 游戏截图
            output_path: 可视化结果保存路径
            **kwargs: 传递给 detect() 的参数
            
        Returns:
            (相对x坐标, 相对y坐标, 弹弓高度, 检测类型)
        """
        result = self.detect(image, **kwargs)
        
        if result is not None and output_path is not None:
            try:
                # 将 PIL Image 转换为 OpenCV 格式
                img_np = np.array(image)
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                
                img_height, img_width = img_bgr.shape[:2]
                
                # 解包结果 (4元组: x, y, height, type)
                rel_x, rel_y, slingshot_height, detection_type = result
                
                # 计算绝对坐标
                center_x = int(rel_x * img_width)
                center_y = int(rel_y * img_height)
                
                # 根据检测类型设置颜色
                if detection_type == 'bird':
                    color = (0, 255, 0)  # 绿色 - bird_on_slingshot
                    label = f"Bird: ({rel_x:.3f}, {rel_y:.3f}) h={slingshot_height}px"
                else:
                    color = (255, 165, 0)  # 橙色 - slingshot
                    label = f"Slingshot: ({rel_x:.3f}, {rel_y:.3f}) h={slingshot_height}px"
                
                # 绘制标记
                cv2.circle(img_bgr, (center_x, center_y), 10, color, 2)
                cv2.circle(img_bgr, (center_x, center_y), 3, (0, 0, 255), -1)
                
                # 绘制十字准星
                cross_size = 20
                cv2.line(img_bgr, (center_x - cross_size, center_y), 
                        (center_x + cross_size, center_y), color, 2)
                cv2.line(img_bgr, (center_x, center_y - cross_size), 
                        (center_x, center_y + cross_size), color, 2)
                
                # 绘制文本标签
                cv2.putText(
                    img_bgr, label, (center_x + 15, center_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
                )
                
                # 添加检测类型说明
                type_label = f"Detection: {detection_type.upper()}"
                cv2.putText(
                    img_bgr, type_label, (center_x + 15, center_y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2
                )
                
                # 保存可视化结果
                cv2.imwrite(output_path, img_bgr)
                logger.info(f"Visualization saved to {output_path}")
                
            except Exception as e:
                logger.error(f"Error saving visualization: {e}")
        
        return result


def test_detector():
    """测试弹弓检测器"""
    # 测试路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(os.path.dirname(current_dir), "images")
    
    test_image_path = os.path.join(images_dir, "whole_window.png")
    output_path = os.path.join(images_dir, "detection_result.png")
    
    if not os.path.exists(test_image_path):
        print(f"Test image not found: {test_image_path}")
        return
    
    # 加载测试图片
    test_image = Image.open(test_image_path)
    
    # 创建检测器
    detector = SlingshotDetector()
    
    # 检测并可视化
    result = detector.detect_with_visualization(
        test_image, 
        output_path=output_path,
        threshold=0.6
    )
    
    if result:
        print(f"Slingshot found at: ({result[0]:.3f}, {result[1]:.3f}), height: {result[2]}px, type: {result[3]}")
        print(f"Visualization saved to: {output_path}")
    else:
        print("Slingshot not found")


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_detector()
