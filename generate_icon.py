"""生成简约风格的应用图标 - Apple 风格"""
from PIL import Image, ImageDraw
import os

def create_icon(size=256):
    """Apple 风格简约图标：浅灰圆角方块 + 抽象 B 形像素图案"""
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
    
    primary = (46, 134, 171, 255)   # 主色蓝
    accent = (240, 142, 74, 255)    # 暖橙色
    
    # 简约像素块图案（5列3行）
    inner = size - 2 * margin
    cell_w = inner // 6
    cell_h = inner // 6
    start_x = margin + cell_w
    start_y = margin + cell_h
    
    pattern = [
        [1, 1, 1],
        [1, 0, 0],
        [1, 1, 1],
        [1, 0, 0],
        [1, 1, 1],
    ]
    colors = [primary, accent]
    
    for row in range(5):
        for col in range(3):
            v = pattern[row][col]
            if v == 0:
                continue
            x0 = start_x + col * cell_w * 1 + (cell_w // 4)
            y0 = start_y + row * cell_h * 1 + (cell_h // 4)
            x1 = x0 + cell_w - (cell_w // 2)
            y1 = y0 + cell_h - (cell_h // 2)
            if x1 <= x0 or y1 <= y0:
                continue
            draw.rounded_rectangle([x0, y0, x1, y1], radius=max(1, cell_w//8), fill=colors[v-1])
    
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