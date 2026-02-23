"""
测试弹弓检测器 - 在测试图片上标注检测结果

用于调试和验证弹弓位置、高度检测的准确性
"""

import os
import sys
import logging
from PIL import Image
import cv2
import numpy as np

# 添加路径以导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(current_dir)))

from slingshot_detector import SlingshotDetector

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def draw_detailed_visualization(image_path: str, output_path: str, detector: SlingshotDetector):
    """
    在图片上绘制详细的检测可视化
    
    Args:
        image_path: 输入图片路径
        output_path: 输出图片路径
        detector: 弹弓检测器实例
    """
    # 加载图片
    pil_image = Image.open(image_path)
    img_np = np.array(pil_image)
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    
    img_height, img_width = img_bgr.shape[:2]
    
    # 执行检测
    result = detector.detect(
        pil_image,
        threshold=0.6,
        scale_range=(0.5, 1.5),
        scale_steps=20,
        prefer_bird=True
    )
    
    if result is None:
        logger.warning(f"No slingshot detected in {image_path}")
        # 在图片上写"未检测到"
        cv2.putText(
            img_bgr, "No Detection", (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3
        )
        cv2.imwrite(output_path, img_bgr)
        return
    
    # 解包结果
    rel_x, rel_y, slingshot_height, detection_type = result
    
    # 计算绝对坐标
    center_x = int(rel_x * img_width)
    center_y = int(rel_y * img_height)
    
    # 设置颜色
    if detection_type == 'bird':
        color = (0, 255, 0)  # 绿色 - bird_on_slingshot
        type_name = "Bird on Slingshot"
    else:
        color = (0, 165, 255)  # 橙色 - slingshot
        type_name = "Slingshot"
    
    # 1. 绘制中心点标记
    cv2.circle(img_bgr, (center_x, center_y), 15, color, 3)
    cv2.circle(img_bgr, (center_x, center_y), 5, (0, 0, 255), -1)
    
    # 2. 绘制十字准星
    cross_size = 40
    cv2.line(img_bgr, (center_x - cross_size, center_y), 
            (center_x + cross_size, center_y), color, 3)
    cv2.line(img_bgr, (center_x, center_y - cross_size), 
            (center_x, center_y + cross_size), color, 3)
    
    # 3. 绘制弹弓高度范围（从中心点向上、向下各延伸 height/2）
    half_height = slingshot_height // 2
    top_y = center_y - half_height
    bottom_y = center_y + half_height
    
    # 绘制高度线
    cv2.line(img_bgr, (center_x - 30, top_y), 
            (center_x + 30, top_y), (255, 0, 255), 2)  # 顶部紫色线
    cv2.line(img_bgr, (center_x - 30, bottom_y), 
            (center_x + 30, bottom_y), (255, 0, 255), 2)  # 底部紫色线
    
    # 绘制垂直高度线
    cv2.line(img_bgr, (center_x - 50, top_y), 
            (center_x - 50, bottom_y), (255, 0, 255), 2)
    
    # 添加箭头
    cv2.arrowedLine(img_bgr, (center_x - 50, top_y), 
                   (center_x - 50, top_y - 20), (255, 0, 255), 2)
    cv2.arrowedLine(img_bgr, (center_x - 50, bottom_y), 
                   (center_x - 50, bottom_y + 20), (255, 0, 255), 2)
    
    # 4. 计算最大拉弓距离
    pull_ratio = 1.4  # 与 config.yaml 中的 slingshot_pull_ratio 保持一致
    max_pull_distance = slingshot_height * pull_ratio
    
    # 5. 添加文本信息
    # 背景矩形使文字更清晰
    info_x = 10
    info_y = 30
    line_height = 35
    
    info_texts = [
        f"Detection Type: {type_name}",
        f"Position: ({rel_x:.3f}, {rel_y:.3f})",
        f"Absolute: ({center_x}, {center_y})",
        f"Slingshot Height: {slingshot_height} px",
        f"Pull Ratio: {pull_ratio}",
        f"Max Pull Distance: {max_pull_distance:.1f} px",
        f"Image Size: {img_width}x{img_height}"
    ]
    
    # 计算背景矩形大小
    max_text_width = max([cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0][0] 
                          for text in info_texts])
    rect_height = len(info_texts) * line_height + 20
    
    # 绘制半透明背景
    overlay = img_bgr.copy()
    cv2.rectangle(overlay, (5, 5), (max_text_width + 25, rect_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, img_bgr, 0.4, 0, img_bgr)
    
    # 绘制文本
    for i, text in enumerate(info_texts):
        y_pos = info_y + i * line_height
        cv2.putText(img_bgr, text, (info_x, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # 6. 在图片右上角标注高度说明
    note_text = "Purple lines show slingshot height"
    text_size = cv2.getTextSize(note_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    note_x = img_width - text_size[0] - 10
    cv2.putText(img_bgr, note_text, (note_x, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
    
    # 保存结果
    cv2.imwrite(output_path, img_bgr)
    logger.info(f"Visualization saved: {output_path}")
    logger.info(f"  Type: {type_name}")
    logger.info(f"  Position: ({center_x}, {center_y})")
    logger.info(f"  Height: {slingshot_height}px")
    logger.info(f"  Max Pull: {max_pull_distance:.1f}px")


def main():
    """主函数 - 处理所有测试图片"""
    # 路径设置
    current_dir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(os.path.dirname(current_dir), "images")
    
    # 创建检测器
    logger.info("Initializing slingshot detector...")
    detector = SlingshotDetector()
    
    # 测试图片列表
    test_images = ["test1.png", "test2.png", "test3.png"]
    
    logger.info(f"\n{'='*60}")
    logger.info("Starting slingshot detection on test images")
    logger.info(f"{'='*60}\n")
    
    # 处理每张测试图片
    for test_image in test_images:
        input_path = os.path.join(images_dir, test_image)
        output_name = f"detection_{test_image}"
        output_path = os.path.join(images_dir, output_name)
        
        if not os.path.exists(input_path):
            logger.warning(f"Test image not found: {input_path}")
            continue
        
        logger.info(f"\nProcessing: {test_image}")
        logger.info(f"-" * 60)
        
        try:
            draw_detailed_visualization(input_path, output_path, detector)
        except Exception as e:
            logger.error(f"Error processing {test_image}: {e}", exc_info=True)
    
    logger.info(f"\n{'='*60}")
    logger.info("Detection complete! Check the output images:")
    for test_image in test_images:
        output_name = f"detection_{test_image}"
        logger.info(f"  - {output_name}")
    logger.info(f"{'='*60}\n")


if __name__ == "__main__":
    main()
