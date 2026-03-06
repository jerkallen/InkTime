# GxEPD2 库 7 色屏研究报告

## 研究日期
2026-03-06

## 一、GxEPD2 库支持的 7.3 寸屏类型

### 1. 四色屏（当前使用）

| 型号 | 驱动类 | 颜色 | 市场名称 |
|------|--------|------|---------|
| GDEY073D46 | `GxEPD2_730c_GDEY073D46` | 4 色：黑、白、红、黄 | 7.3" ACeP (4-color) |

### 2. 七色屏（改造目标）

| 型号 | 驱动类 | 颜色 | 市场名称 |
|------|--------|------|---------|
| ACeP730 | `GxEPD2_730c_ACeP_730` | **7 色**：黑、白、红、黄、橙、蓝、绿 | 7.3" ACeP (7-color) |

### 3. 硬件兼容性

✅ **引脚定义完全相同**（49-pin FPC）
✅ **SPI 通信协议相同**
✅ **分辨率相同**（800×480）
✅ **无需改动硬件电路**

---

## 二、BIN 文件格式对比（关键！）

### 当前 4 色屏格式

**Python 端生成**：
```python
# 文件大小：480 × 800 × 1 字节 = 384,000 字节（384KB）
PALETTE = [
    (0, 0, 0),      # 黑色 → 0
    (255, 255, 255), # 白色 → 1
    (255, 0, 0),     # 红色 → 2
    (255, 255, 0),   # 黄色 → 3
]

def image_to_palette_bin(img):
    data = bytearray(CANVAS_WIDTH * CANVAS_HEIGHT)
    for y in range(CANVAS_HEIGHT):
        for x in range(CANVAS_WIDTH):
            idx = color_index  # 0, 1, 2, 3
            data[y * CANVAS_WIDTH + x] = idx
    return bytes(data)
```

**ESP32 端读取**：
```cpp
// 直接读取，1 字节 = 1 像素
uint8_t pixel_value = buffer[i];
// 0=黑, 1=白, 2=红, 3=黄
```

### 7 色屏格式（改造后）

**Python 端生成**（需要修改）：
```python
# 文件大小：480 × 800 × 2 字节 = 768,000 字节（768KB）
# 需要生成 2 个数据层：black + color

def image_to_7color_bin(img):
    black_data = bytearray(CANVAS_WIDTH * CANVAS_HEIGHT)
    color_data = bytearray(CANVAS_WIDTH * CANVAS_HEIGHT)
    
    for y in range(CANVAS_HEIGHT):
        for x in range(CANVAS_WIDTH):
            color_index = get_7color_index(img.getpixel((x, y)))
            # 分解为 black 和 color 两层
            black_data[y * CANVAS_WIDTH + x] = extract_black(color_index)
            color_data[y * CANVAS_WIDTH + x] = extract_color(color_index)
    
    # 组合成一个文件：先 black 层，再 color 层
    return bytes(black_data) + bytes(color_data)
```

**ESP32 端读取**（GxEPD2 已实现）：
```cpp
// GxEPD2_730c_ACeP_730.cpp 中的实现
void GxEPD2_730c_ACeP_730::writeImage(const uint8_t* black, const uint8_t* color, ...)
{
    // black：1 字节/像素（黑白层）
    // color：1 字节/像素（颜色层）
    // 输出时组合成 4 位对（每对 2 像素）
    for (int k = 0; k < 4; k++)
    {
        uint8_t out_data = 0x00;
        for (int l = 0; l < 2; l++)
        {
            out_data <<= 4;
            if (!(color_data & 0x80)) out_data |= 0x04;
            else out_data |= black_data & 0x80 ? 0x01 : 0x00;
            black_data <<= 1;
            color_data <<= 1;
        }
        _transfer(out_data);
    }
}
```

---

## 三、7 色调色板（需根据实际屏幕规格确认）

根据 ACeP 7 色屏的通用规格，预期的 7 种颜色：

| 颜色 | RGB 值 | 用途 |
|------|--------|------|
| 黑色 | (0, 0, 0) | 文字、边框 |
| 白色 | (255, 255, 255) | 背景 |
| 红色 | (255, 0, 0) | 强调、警告 |
| 黄色 | (255, 255, 0) | 高亮、注释 |
| 橙色 | (255, 165, 0) | 中间色 |
| 蓝色 | (0, 0, 255) | 天空、水 |
| 绿色 | (0, 255, 0) | 植物、自然 |

**注意**：实际颜色值需要参考屏幕数据手册，可能需要微调。

---

## 四、代码改造关键点

### 1. ESP32 固件（相对简单）

**修改前**（4 色）：
```cpp
#include <GxEPD2_7C.h>
GxEPD2_7C<
  GxEPD2_730c_GDEY073D46,
  GxEPD2_730c_GDEY073D46::HEIGHT / 4  // /4 是因为 4 色
> display(...);
```

**修改后**（7 色）：
```cpp
#include <GxEPD2_7C.h>
GxEPD2_7C<
  GxEPD2_730c_ACeP_730,
  GxEPD2_730c_ACeP_730::HEIGHT / 7  // /7 是因为 7 色
> display(...);
```

**数据读取**（需要修改）：
```cpp
// 修改前：读取 1 个 BIN 文件（384KB）
uint8_t* black_data = buffer;
uint8_t* color_data = nullptr;

// 修改后：读取 2 个数据层（768KB）
uint8_t* black_data = buffer;
uint8_t* color_data = buffer + 384000;  // 指向第二层

display.writeImage(black_data, color_data, ...);
```

### 2. Python 后端（核心改造）

**关键改动**：

1. **定义 7 色调色板**
```python
SEVEN_COLOR_PALETTE = [
    (0, 0, 0),        # 黑色 → 0
    (255, 255, 255),  # 白色 → 1
    (255, 0, 0),      # 红色 → 2
    (255, 255, 0),    # 黄色 → 3
    (255, 165, 0),    # 橙色 → 4
    (0, 0, 255),      # 蓝色 → 5
    (0, 255, 0),      # 绿色 → 6
]
```

2. **实现 7 色 Floyd-Steinberg Dither**
```python
def apply_seven_color_dither(img):
    """7 色抖动算法"""
    # 从 4 色改为 7 色查找
    # 颜色量化：找到最接近的 7 色之一
    # 抖动：Floyd-Steinberg 误差扩散
    pass
```

3. **修改 BIN 文件生成**
```python
def image_to_7color_bin(img):
    """生成 7 色屏的 BIN 文件（2 层）"""
    width, height = img.size
    black_layer = bytearray(width * height)
    color_layer = bytearray(width * height)
    
    for y in range(height):
        for x in range(width):
            r, g, b = img.getpixel((x, y))
            color_idx = find_nearest_7color(r, g, b)
            
            # 分解为 black 和 color
            black_layer[y * width + x] = extract_black_bit(color_idx)
            color_layer[y * width + x] = extract_color_bits(color_idx)
    
    # 组合：先 black 层，再 color 层
    return bytes(black_layer) + bytes(color_layer)
```

4. **BIN 文件大小变化**
```python
# 修改前：384,000 字节（384KB）
# 修改后：768,000 字节（768KB）
```

---

## 五、技术难点与解决方案

### 难点 1：颜色映射算法

**问题**：RGB → 7 色的映射比 4 色复杂

**解决方案**：
- 使用欧氏距离计算颜色相似度
- 预计算 7 色到 RGB 的距离矩阵
- 优化查找速度（K-D 树或哈希表）

### 难点 2：BIN 文件格式不兼容

**问题**：7 色屏需要 2 字节/像素，4 色只需 1 字节/像素

**解决方案**：
- Python 端生成 2 层数据（black + color）
- ESP32 端分离读取
- 文件大小从 384KB → 768KB

### 难点 3：PSRAM 需求

**问题**：7 色屏需要更多内存

**解决方案**：
- 确认 ESP32-S3-N8R8 的 PSRAM（8MB）足够
- 优化内存使用（分页传输）
- GxEPD2 库已实现分页支持

---

## 六、实施建议

### 方案 A：渐进式改造（推荐）

1. **第一步**：先修改 ESP32 固件，使用 7 色屏驱动类
2. **第二步**：实现 Python 7 色渲染，保持 BIN 格式兼容（先用 4 色测试）
3. **第三步**：修改 BIN 文件格式为 2 层
4. **第四步**：端到端测试和调优

### 方案 B：一次性改造

1. 同时修改 ESP32 和 Python 代码
2. 直接生成 7 色 2 层 BIN 文件
3. 测试和调试

---

## 七、验证清单

### ESP32 固件
- [ ] 驱动类替换为 `GxEPD2_730c_ACeP_730`
- [ ] 编译通过
- [ ] 内存使用正常（PSRAM）
- [ ] 刷新时序正确

### Python 后端
- [ ] 7 色调色板定义正确
- [ ] 7 色 Dither 算法实现
- [ ] BIN 文件生成正确（2 层，768KB）
- [ ] 预览 PNG 正常

### 集成测试
- [ ] ESP32 能正确下载 BIN 文件
- [ ] 7 种颜色正确显示
- [ ] 图像质量符合预期
- [ ] 刷新速度可接受

---

## 八、参考资料

### GxEPD2 库
- GitHub：https://github.com/ZinggJM/GxEPD2
- 7 色屏示例：`GxEPD2_730c_ACeP_730`
- 关键文件：
  - `src/epd7c/GxEPD2_730c_ACeP_730.h`
  - `src/epd7c/GxEPD2_730c_ACeP_730.cpp`

### 屏幕规格
- Waveshare 7.3" ACeP 7-Color：https://www.waveshare.com/product/displays/e-paper/7.3inch-e-paper-f.htm
- Good Display：https://www.good-display.com/product/442.html

### Python 图像处理
- Pillow 文档：https://pillow.readthedocs.io/
- Floyd-Steinberg 算法：https://en.wikipedia.org/wiki/Floyd–Steinberg_dithering

---

## 九、下一步行动

1. ✅ **完成 GxEPD2 库研究**（本文档）
2. ⏳ **实现 Python 7 色 Dither 算法**
3. ⏳ **修改 BIN 文件生成逻辑**
4. ⏳ **改造 ESP32 固件**
5. ⏳ **本地测试**
6. ⏳ **部署到阿里云**

---

**研究完成时间**：2026-03-06
**研究者**：Jedi（Allen 的 AI 助手）
**GitHub 仓库**：https://github.com/jerkallen/InkTime
