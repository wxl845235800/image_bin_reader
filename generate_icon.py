"""生成简约风格的应用图标 - 双向转换寓意"""
from PIL import Image, ImageDraw
import os

def create_icon(size=256):
    """简约图标：浅灰圆角方块 + 双向箭头 ↻ 寓意转换"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    margin = size // 8
    radius = size // 4
    
    # 浅灰背景
    bg_color = (240, 242, 245, 255)
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius, fill=bg_color
    )
    
    primary = (0, 113, 227, 255)    # Apple 蓝
    accent = (255, 159, 10, 255)     # Apple 橙
    
    cx = size // 2
    cy = size // 2
    r = size // 5
    
    # 画一个简约的双向循环箭头 ↻
    # 用两个半圆 + 箭头表示转换
    
    # 外圈 - 蓝色半圆（上）
    draw.arc([cx - r, cy - r, cx + r, cy + r], 
             start=135, end=405, fill=primary, width=max(3, size//20))
    
    # 外圈 - 橙色半圆（下）
    draw.arc([cx - r, cy - r, cx + r, cy + r], 
             start=-45, end=135, fill=accent, width=max(3, size//20))
    
    # 蓝色箭头（右上）
    arrow_size = max(4, size // 16)
    ax = cx + int(r * 0.7)
    ay = cy - int(r * 0.7)
    draw.polygon([
        (ax, ay - arrow_size),
        (ax + arrow_size, ay),
        (ax, ay + arrow_size),
    ], fill=primary)
    
    # 橙色箭头（左下）
    ax2 = cx - int(r * 0.7)
    ay2 = cy + int(r * 0.7)
    draw.polygon([
        (ax2, ay2 - arrow_size),
        (ax2 - arrow_size, ay2),
        (ax2, ay2 + arrow_size),
    ], fill=accent)
    
    return img

def main():
    sizes = [16, 32, 48, 64, 128, 256]
    icon_images = [create_icon(s) for s in sizes]
    
    ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_icon.ico')
    icon_images[0].save(ico_path, format='ICO', sizes=[(s, s) for s in sizes], append_images=icon_images[1:])
    print(f"图标已生成: {ico_path}")
    
    png_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_icon.png')
    create_icon(256).save(png_path)
    print(f"PNG 预览: {png_path}")

if __name__ == '__main__':
    main()