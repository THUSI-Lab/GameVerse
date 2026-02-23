import cv2
from PIL import Image
import numpy as np
import os
import math

# template 图片截图时的参考分辨率
REF_W = 1280
REF_H = 980

# 站点尺寸范围(基于1280x980分辨率)
# 游戏进行过程中站点会变小，这里用一个较小的阈值
MIN_STATION_AREA = 600    # 最小面积(像素²)

def find_ui_template(screen_image, template_image, current_resolution, threshold=0.8):
    """
    在屏幕截图中查找 UI 模板

    Args:
        screen_image (numpy.ndarray): 屏幕截图
        template_image (numpy.ndarray): UI 模板图像
        current_resolution (tuple): 当前屏幕分辨率 (width, height)
        threshold (float): 匹配阈值

    Returns:
        dict: 包含中心坐标和边界框的字典 {"cx": x, "cy": y, "bbox": (x, y, w, h)} 或 None 如果未找到
    """
    current_w, current_h = current_resolution
    scale_x = current_w / REF_W
    scale_y = current_h / REF_H
    # 缩放模板图以适应分辨率变化
    new_w = int(template_image.shape[1] * scale_x)
    new_h = int(template_image.shape[0] * scale_y)
    resized_template = cv2.resize(template_image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    if isinstance(screen_image, Image.Image):
        screen_np = np.array(screen_image)
        screen_image = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
    result = cv2.matchTemplate(screen_image, resized_template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= threshold:
        x, y = max_loc
        center_x = x + new_w // 2
        center_y = y + new_h // 2
        return {"cx": center_x, "cy": center_y, "bbox": (x, y, new_w, new_h)}
    return None

def find_stations(image, ui_regions=None, padding=10):
    """
    检测游戏中的站点位置
    
    Args:
        image: 游戏截图（PIL.Image或numpy.ndarray）
        ui_regions: UI图标区域列表，格式为 [(x, y, w, h), ...]
        padding: UI区域mask的扩展像素数
    
    Returns:
        list: 站点列表 [{'cx': x, 'cy': y, 'bbox': (x, y, w, h)}, ...]
    """
    if isinstance(image, Image.Image):
        img_np = np.array(image)
        image = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 如果提供了UI区域，先创建mask将这些区域涂白（排除检测）
    if ui_regions:
        for bbox in ui_regions:
            x, y, w, h = bbox
            # 扩展区域以确保完全覆盖
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(gray.shape[1], x + w + padding)
            y2 = min(gray.shape[0], y + h + padding)
            # 将UI区域设为白色（255），这样在二值化后不会被检测为站点
            gray[y1:y2, x1:x2] = 255


    # 二值化：提取深色物体（站点边框 + 乘客）
    # 使用反向阈值，因为我们关注的是黑色的东西
    # 像素值小于 100 的变白(255)，其余变黑(0)
    _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

    # 轮廓查找
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    stations = []

    print(f"检测到 {len(contours)} 个潜在轮廓")

    for cnt in contours:
        # --- 过滤逻辑 ---
        
        # A. 面积过滤：太小的通常是噪点或很小的乘客
        area = cv2.contourArea(cnt)
        if area < MIN_STATION_AREA: # 阈值根据分辨率调整
            continue
            
        # B. 获取边界框
        x, y, w, h = cv2.boundingRect(cnt)
            
        # 计算中心点坐标
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
        else:
            cX, cY = x + w//2, y + h//2

        y_start, y_end = max(0, cY-1), min(h, cY+2)
        x_start, x_end = max(0, cX-1), min(w, cX+2)
        center_region = gray[y_start:y_end, x_start:x_end]
        
        center_brightness = np.mean(center_region)

        # 判定标准：
        # 站点是空心的 -> 中心是地图背景色 -> 亮度高 (接近255)
        # 乘客是实心的 -> 中心是黑色 -> 亮度低 (接近0)
        if center_brightness < 50:
            continue
        
        stations.append({'cx': cX, 'cy': cY, 'bbox': (x, y, w, h)})
            
    return stations