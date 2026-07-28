# 图像 BIN 转换工具

本地 GUI 工具：图像 ↔ BIN 二进制转换。

## 功能

- **图像 → BIN**：JPG/PNG/BMP/GIF/TIFF → 纯 RGB planar 二进制（无文件头）
- **BIN → 图像**：纯二进制 → 图像（支持 uint8 / float32）
- **拖拽加载**：将文件拖入窗口任意位置即可加载
- **智能尺寸推测**：自动根据文件大小推测 W/H，支持精确方形、16:9 等常见比例
- **实时预览**：加载后即时显示图像预览
- **W/H 联动**：手动修改 W 或 H 时，另一个尺寸会根据文件大小自动计算
- **多格式输出**：BMP / JPG / PNG / TIFF
- **存储格式可选**：uint8 或 float32
- **归一化选项**：导出 float32 时可选择将像素值除以 255，存为 0.0~1.0
- **自动放大**：当 float32 数据的数值范围 ≤1 时，自动乘以放大倍数转回 0~255 显示
- **自定义放大倍数**：可设置 0~1023 的放大倍数，适应不同数据范围

## 使用

### 图像转 BIN

1. 拖入图像文件，或点击「浏览」选择文件
2. 设置目标尺寸、缩放/裁剪模式、存储格式
3. 点击「▶ 开始转换」
4. 输出为 `.bin` 文件

### BIN 转图像

1. 拖入 `.bin` 文件，或点击「浏览」选择文件
2. 选择「以 uint8 形式读取」或「以 float32 形式读取」
3. 查看顶部推测的 W/H，可直接修改；修改一个，另一个会自动计算
4. 如需调整 float32 的显示效果，可修改「放大倍数」（默认 255）
5. 选择输出图片格式（默认 BMP）
6. 点击「▶ 开始转换」

## BIN 格式

纯 RGB planar 数据，无文件头：

```
RRR...GGG...BBB...
```

- `uint8`：文件大小 = W × H × 3 字节
- `float32`：文件大小 = W × H × 12 字节

### 放大倍数说明

- 当使用「以 float32 形式读取」时，程序会计算数据的**均值**，如果均值 ≤1，说明整体数据范围较小，会自动乘以放大倍数（默认 255）将数据映射到 0~255 范围进行显示
- 这样即使数据中有个别超出 0~1 的 outlier（例如范围 -0.5~1.6），只要整体均值 ≤1 仍会触发自动放大
- 可在「BIN 读取参数」区域手动调整放大倍数（范围 0~1023），以适应不同的数据分布

## 开发

```bash
pip install tkinterdnd2 pillow numpy pyinstaller
python img2bin.py
```

## 打包

```bash
pyinstaller --onefile --windowed --name "图像bin显示" --hidden-import tkinterdnd2 --hidden-import numpy --collect-data tkinterdnd2 --collect-binaries tkinterdnd2 --collect-binaries numpy img2bin.py
```

打包完成后，可执行文件位于：

```
dist/图像bin显示.exe
```

## 项目结构

```
.
├── img2bin.py          # 主程序源码
├── README.md           # 项目说明
├── dist/               # 打包后的 EXE
│   └── 图像bin显示.exe
└── .gitignore
```

## 声明

本项目完全由 **Cline**（AI 编程助手）生成，包括界面设计、功能实现、打包和文档。

- 工具：https://cline.bot
- 完全 AI 生成，无人工修改

## License

MIT