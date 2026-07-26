# 图像 BIN 转换工具

本地 GUI 工具：图像 ↔ BIN 二进制转换。

## 功能

- 图像 → BIN：JPG/PNG/BMP → 纯 RGB planar 二进制（无文件头）
- BIN → 图像：纯二进制 → 图像（支持 uint8/float32）
- 拖拽加载，智能尺寸推测，多格式输出（BMP/JPG/PNG/TIFF）

## 使用

### 图像转 BIN
1. 拖入图像文件
2. 设置目标尺寸、模式、存储格式
3. 点击「▶ 开始转换」

### BIN 转图像
1. 拖入 .bin 文件
2. 确认推测尺寸（显示 uint8 + float32）
3. 选择输出格式（默认 BMP）
4. 点击「▶ 开始转换」

## BIN 格式

纯 RGB planar 数据，无文件头：
```
RRR...GGG...BBB...
```
- uint8：文件大小 = W × H × 3
- float32：文件大小 = W × H × 12

## 开发

```bash
pip install tkinterdnd2 pillow numpy pyinstaller
python img2bin.py
```

打包：
```bash
pyinstaller --onefile --windowed --name "图像bin显示" --hidden-import tkinterdnd2 --hidden-import numpy --collect-data tkinterdnd2 --collect-binaries tkinterdnd2 --collect-binaries numpy img2bin.py
```

## 声明

本项目完全由 **Cline**（AI 编程助手）生成，包括界面设计、功能实现、打包和文档。
- 工具：https://cline.bot
- 完全 AI 生成，无人工修改

## License

MIT