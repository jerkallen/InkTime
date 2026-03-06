# 7 色墨水屏渲染实现文档

## 实现日期
2026-03-06

## 一、实现功能

### ✅ 已完成
1. **7 色调色板定义** - 黑、白、红、黄、橙、蓝、绿
2. **7 色 Floyd-Steinberg Dither 算法** - 颜色量化 + 误差扩散
3. **2 层 BIN 文件生成** - black 层 + color 层
4. **测试脚本** - 完整的测试流程

### 📊 测试结果
```
✅ 源图像: test/test_7color_source.png
✅ 抖动图像: test/test_7color_dithered.png
✅ BIN 文件: test/test_7color.bin
✅ 文件大小: 768,000 字节 (750 KB)
```

---

## 二、代码结构

### 文件: `render_7color.py`

```
render_7color.py (6,504 字节)
├── SEVEN_COLOR_PALETTE          # 7 色调色板定义
├── nearest_seven_color()        # 颜色查找（欧氏距离）
├── apply_seven_color_dither()   # Floyd-Steinberg 抖动
├── color_index_to_black_color() # 7 色索引 → 2 层映射
├── image_to_7color_bin()        # 生成 2 层 BIN 文件
├── create_test_image()          # 测试图像生成
└── main()                       # 主函数（测试流程）
```

---

## 三、7 色调色板

| 索引 | 颜色 | RGB 值 | 用途 |
|------|------|--------|------|
| 0 | 黑色 | (0, 0, 0) | 文字、边框 |
| 1 | 白色 | (255, 255, 255) | 背景 |
| 2 | 红色 | (255, 0, 0) | 强调、警告 |
| 3 | 黄色 | (255, 255, 0) | 高亮、注释 |
| 4 | 橙色 | (255, 165, 0) | 中间色 |
| 5 | 蓝色 | (0, 0, 255) | 天空、水 |
| 6 | 绿色 | (0, 255, 0) | 植物、自然 |

---

## 四、BIN 文件格式

### 文件结构
```
+-------------------+
| Black Layer       | 480 × 800 = 384,000 字节
| (1 byte/pixel)    |
+-------------------+
| Color Layer       | 480 × 800 = 384,000 字节
| (1 byte/pixel)    |
+-------------------+
Total: 768,000 bytes (750 KB)
```

### 数据层映射

| 颜色索引 | Black Layer | Color Layer | 说明 |
|----------|-------------|-------------|------|
| 0 (黑)   | 1 | 0 | 黑色像素 |
| 1 (白)   | 0 | 0 | 白色像素 |
| 2 (红)   | 0 | 2 | 红色像素 |
| 3 (黄)   | 0 | 3 | 黄色像素 |
| 4 (橙)   | 0 | 4 | 橙色像素 |
| 5 (蓝)   | 0 | 5 | 蓝色像素 |
| 6 (绿)   | 0 | 6 | 绿色像素 |

**注意**: 这是简化的映射规则，实际需要根据 GxEPD2 库的实现调整。

---

## 五、使用方法

### 1. 直接运行测试

```bash
cd /Users/allen/Documents/Jedi/InkTime
python3 render_7color.py
```

### 2. 集成到现有代码

在 `render_daily_photo.py` 中：

```python
# 替换 4 色调色板
# from: PALETTE = [(0,0,0), (255,255,255), (200,0,0), (220,180,0)]
# to:   from render_7color import SEVEN_COLOR_PALETTE

# 替换 Dither 算法
# from: img_dithered = apply_four_color_dither(img)
# to:   from render_7color import apply_seven_color_dither
#       img_dithered = apply_seven_color_dither(img)

# 替换 BIN 生成
# from: bin_data = image_to_palette_bin(img_dithered)
# to:   from render_7color import image_to_7color_bin
#       bin_data = image_to_7color_bin(img_dithered)
```

---

## 六、性能测试

### 测试环境
- **CPU**: Apple M1 (arm64)
- **Python**: 3.12.3
- **图像大小**: 480 × 800

### 性能数据

| 步骤 | 耗时 | 说明 |
|------|------|------|
| 创建测试图像 | < 0.1s | PIL 基本操作 |
| 7 色 Dither | ~2-3s | 480×800 像素 × 7 色查找 |
| BIN 生成 | < 0.1s | 直接内存操作 |
| **总计** | **~2-3s** | 可接受 |

---

## 七、下一步工作

### 立即可做
1. ✅ **Python 7 色渲染** - 已完成
2. ⏳ **修改 render_daily_photo.py** - 集成 7 色渲染
3. ⏳ **本地测试** - 使用真实照片测试
4. ⏳ **ESP32 固件改造** - 修改驱动类和数据读取逻辑

### 需要验证
1. **颜色映射规则** - 需要根据实际屏幕规格调整
2. **BIN 格式兼容性** - 需要在 ESP32 上测试
3. **显示效果** - 需要在实际屏幕上验证

---

## 八、技术要点

### 1. Floyd-Steinberg 抖动算法
```python
# 误差扩散模式
#        *   7/16
#   3/16 5/16 1/16

# 误差计算
er = r - pr  # 原始值 - 量化值
eg = g - pg
eb = b - pb

# 扩散到相邻像素
err_r[x + 1] += er * (7.0 / 16.0)     # 右
next_err_r[x - 1] += er * (3.0 / 16.0)  # 左下
next_err_r[x] += er * (5.0 / 16.0)      # 下
next_err_r[x + 1] += er * (1.0 / 16.0)  # 右下
```

### 2. 颜色查找优化
```python
# 当前: 线性查找 (7 次比较/像素)
def nearest_seven_color(r, g, b):
    for i, (pr, pg, pb) in enumerate(SEVEN_COLOR_PALETTE):
        dist = (r-pr)**2 + (g-pg)**2 + (b-pb)**2
        if dist < best_dist:
            best_dist = dist
            best_idx = i

# 可优化: 预计算距离矩阵或使用 K-D 树
```

### 3. 内存使用
```python
# 误差数组（3 个颜色 × 480 像素）
err_r = [0.0] * 480   # 3.8 KB
err_g = [0.0] * 480   # 3.8 KB
err_b = [0.0] * 480   # 3.8 KB
next_err_* 同上

# 总内存: ~23 KB（可接受）
```

---

## 九、参考资料

### GxEPD2 库
- GitHub: https://github.com/ZinggJM/GxEPD2
- 7 色屏示例: `GxEPD2_730c_ACeP_730`

### Floyd-Steinberg 算法
- Wikipedia: https://en.wikipedia.org/wiki/Floyd–Steinberg_dithering

### Python 图像处理
- Pillow: https://pillow.readthedocs.io/

---

## 十、问题排查

### 常见问题

**Q1: BIN 文件大小不对？**
- 检查: `480 × 800 × 2 = 768,000` 字节
- 原因: 可能是 4 色模式（384,000 字节）

**Q2: 颜色显示不正确？**
- 检查: `color_index_to_black_color()` 映射规则
- 调整: 根据 GxEPD2 库实现修改

**Q3: 抖动效果不理想？**
- 原因: 7 色调色板颜色值可能不准确
- 解决: 根据实际屏幕规格调整 RGB 值

---

**实现完成时间**: 2026-03-06
**实现者**: Jedi (Allen 的 AI 助手)
**GitHub 仓库**: https://github.com/jerkallen/InkTime
