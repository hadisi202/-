#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
二维码处理器
负责二维码的生成、识别和包裹号验证
"""

import re
import json
import os
import qrcode
import cv2
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pyzbar import pyzbar
from PIL import Image, ImageDraw, ImageFont


class QRCodeHandler:
    """二维码处理器类"""
    
    def __init__(self, settings_file: str = "qr_settings.json"):
        """
        初始化二维码处理器
        
        Args:
            settings_file: 设置文件路径
        """
        self.settings_file = settings_file
        self.settings = self._load_settings()
        
        # 默认包裹号格式
        self.default_patterns = [
            r'^[A-Z]{2,4}\d{8,12}$',  # 标准包装单号
            r'^HDS\d{11}$',           # 自定义格式
            r'^\d{10,15}$',           # 纯数字
        ]
    
    def _load_settings(self) -> Dict[str, Any]:
        """加载设置"""
        default_settings = {
            "package_patterns": [
                r'^[A-Z]{2,4}\d{8,12}$',
                r'^HDS\d{11}$',
                r'^\d{10,15}$'
            ],
            "custom_prefix": "HDS",
            "auto_generate": True,
            "qr_size": 200,
            "qr_border": 4,
            "last_sequence": 0
        }
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # 合并默认设置和加载的设置
                    default_settings.update(loaded_settings)
            return default_settings
        except Exception as e:
            print(f"加载设置失败: {e}")
            return default_settings
    
    def _save_settings(self):
        """保存设置"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存设置失败: {e}")
    
    def validate_package_code(self, package_code: str) -> bool:
        """
        验证包裹号格式
        
        Args:
            package_code: 包裹号
            
        Returns:
            bool: 是否有效
        """
        if not package_code or not isinstance(package_code, str):
            return False
        
        package_code = package_code.strip().upper()
        
        # 检查自定义格式
        patterns = self.settings.get("package_patterns", self.default_patterns)
        
        for pattern in patterns:
            if re.match(pattern, package_code):
                return True
        
        return False
    
    def generate_custom_package_code(self) -> str:
        """
        生成自定义包裹号
        格式: HDS + YYYYMMDD + XXX (3位序号)
        
        Returns:
            str: 生成的包裹号
        """
        prefix = self.settings.get("custom_prefix", "HDS")
        date_str = datetime.now().strftime("%Y%m%d")
        
        # 获取并更新序号
        sequence = self.settings.get("last_sequence", 0) + 1
        self.settings["last_sequence"] = sequence
        self._save_settings()
        
        # 生成包裹号
        package_code = f"{prefix}{date_str}{sequence:03d}"
        return package_code
    
    def create_qr_code(self, data: str, size: int = None, border: int = None) -> Image.Image:
        """
        创建二维码图片
        
        Args:
            data: 要编码的数据
            size: 二维码大小
            border: 边框大小
            
        Returns:
            PIL.Image: 二维码图片
        """
        if size is None:
            size = self.settings.get("qr_size", 200)
        if border is None:
            border = self.settings.get("qr_border", 4)
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=border,
        )
        
        qr.add_data(data)
        qr.make(fit=True)
        
        # 创建二维码图片
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # 调整大小
        qr_img = qr_img.resize((size, size), Image.Resampling.LANCZOS)
        
        return qr_img
    
    def create_qr_code_with_text(self, package_code: str, additional_info: str = "") -> Image.Image:
        """
        创建带文字的二维码图片
        
        Args:
            package_code: 包裹号
            additional_info: 附加信息
            
        Returns:
            PIL.Image: 带文字的二维码图片
        """
        # 创建二维码
        qr_size = self.settings.get("qr_size", 200)
        qr_img = self.create_qr_code(package_code, qr_size)
        
        # 计算总图片大小（二维码 + 文字区域）
        text_height = 60
        total_height = qr_size + text_height
        
        # 创建新图片
        img = Image.new('RGB', (qr_size, total_height), 'white')
        
        # 粘贴二维码
        img.paste(qr_img, (0, 0))
        
        # 添加文字
        draw = ImageDraw.Draw(img)
        
        try:
            # 尝试使用系统字体
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            # 使用默认字体
            font = ImageFont.load_default()
        
        # 绘制包裹号
        text_y = qr_size + 10
        draw.text((10, text_y), f"包裹号: {package_code}", fill='black', font=font)
        
        # 绘制附加信息
        if additional_info:
            draw.text((10, text_y + 25), additional_info, fill='black', font=font)
        
        return img
    
    def scan_qr_code_from_image(self, image_path: str) -> List[str]:
        """
        从图片文件中扫描二维码
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            List[str]: 扫描到的二维码数据列表
        """
        try:
            # 读取图片
            image = cv2.imread(image_path)
            if image is None:
                return []
            
            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 扫描二维码
            decoded_objects = pyzbar.decode(gray)
            
            results = []
            for obj in decoded_objects:
                data = obj.data.decode('utf-8')
                results.append(data)
            
            return results
            
        except Exception as e:
            print(f"扫描二维码失败: {e}")
            return []
    
    def scan_qr_code_from_camera(self, camera_index: int = 0, timeout: int = 30) -> Optional[str]:
        """
        从摄像头扫描二维码
        
        Args:
            camera_index: 摄像头索引
            timeout: 超时时间（秒）
            
        Returns:
            Optional[str]: 扫描到的二维码数据，如果失败返回None
        """
        try:
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                print("无法打开摄像头")
                return None
            
            start_time = datetime.now()
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 扫描二维码
                decoded_objects = pyzbar.decode(frame)
                
                for obj in decoded_objects:
                    data = obj.data.decode('utf-8')
                    cap.release()
                    cv2.destroyAllWindows()
                    return data
                
                # 显示摄像头画面
                cv2.imshow('QR Code Scanner', frame)
                
                # 检查超时
                if (datetime.now() - start_time).seconds > timeout:
                    break
                
                # 按ESC退出
                if cv2.waitKey(1) & 0xFF == 27:
                    break
            
            cap.release()
            cv2.destroyAllWindows()
            return None
            
        except Exception as e:
            print(f"摄像头扫描失败: {e}")
            return None
    
    def preprocess_image_for_scanning(self, image: np.ndarray) -> np.ndarray:
        """
        预处理图片以提高二维码识别率
        
        Args:
            image: 输入图片
            
        Returns:
            np.ndarray: 处理后的图片
        """
        # 转换为灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # 高斯模糊
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 自适应阈值
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        return thresh
    
    def get_package_patterns(self) -> List[str]:
        """获取包裹号格式列表"""
        return self.settings.get("package_patterns", self.default_patterns)
    
    def add_package_pattern(self, pattern: str) -> bool:
        """
        添加包裹号格式
        
        Args:
            pattern: 正则表达式格式
            
        Returns:
            bool: 添加是否成功
        """
        try:
            # 验证正则表达式
            re.compile(pattern)
            
            patterns = self.settings.get("package_patterns", [])
            if pattern not in patterns:
                patterns.append(pattern)
                self.settings["package_patterns"] = patterns
                self._save_settings()
                return True
            return False
            
        except re.error:
            print(f"无效的正则表达式: {pattern}")
            return False
    
    def remove_package_pattern(self, pattern: str) -> bool:
        """
        移除包裹号格式
        
        Args:
            pattern: 要移除的格式
            
        Returns:
            bool: 移除是否成功
        """
        patterns = self.settings.get("package_patterns", [])
        if pattern in patterns:
            patterns.remove(pattern)
            self.settings["package_patterns"] = patterns
            self._save_settings()
            return True
        return False
    
    def update_settings(self, **kwargs):
        """
        更新设置
        
        Args:
            **kwargs: 要更新的设置项
        """
        self.settings.update(kwargs)
        self._save_settings()
    
    def get_settings(self) -> Dict[str, Any]:
        """获取当前设置"""
        return self.settings.copy()
    
    def extract_package_codes_from_text(self, text: str) -> List[str]:
        """
        从文本中提取包裹号
        
        Args:
            text: 输入文本
            
        Returns:
            List[str]: 提取到的包裹号列表
        """
        package_codes = []
        patterns = self.get_package_patterns()
        
        for pattern in patterns:
            matches = re.findall(pattern, text.upper())
            package_codes.extend(matches)
        
        # 去重并保持顺序
        unique_codes = []
        for code in package_codes:
            if code not in unique_codes:
                unique_codes.append(code)
        
        return unique_codes