#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
7 色墨水屏渲染脚本
- 支持黑、白、红、黄、橙、蓝、绿 7 种颜色
- 使用 Floyd-Steinberg 抖动算法
- 生成 2 层 BIN 文件（black 层 + color 层）
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple
from PIL import Image, ImageDraw
import numpy as np


# ========== 7 色调色板 ==========

SEVEN_COLOR_PALETTE = [
    (0, 0, 0),         # 0 = 黑
    (255, 255, 255),   # 1 = 白
    (255, 0, 0),       # 2 = 红
    (255, 255, 0),     # 3 = 黄
    (255, 165, 0),     # 4 = 橙
    (0, 0, 255),       # 5 = 蓝
    (0, 255, 0),       # 6 = 绿
]


def nearest_seven_color(r: float, g: float, b: float) -> Tuple[int, int, int, int]:
    """
    返回 (idx, pr, pg, pb)，idx 为 SEVEN_COLOR_PALETTE 中最近颜色的索引。
    使用欧氏距离计算颜色相似度。
    """
    best_idx = 0
    best_dist = float("inf")
    for i, (pr, pg, pb) in enumerate(SEVEN_COLOR_PALETTE):
        dr = r - pr
        dg = g - pg
        db = b - pb
        dist = dr * dr + dg * dg + db * db
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    pr, pg, pb = SEVEN_COLOR_PALETTE[best_idx]
    return best_idx, pr, pg, pb


def apply_seven_color_dither(img: Image.Image) -> Image.Image:
    """
    对图像做 Floyd–Steinberg 抖动，量化到七种颜色。
    """
    img = img.convert("RGB")
    w, h = img.size
    pixels = img.load()

    err_r = [0.0] * w
    err_g = [0.0] * w
    err_b = [0.0] * w
    next_err_r = [0.0] * w
    next_err_g = [0.0] * w
    next_err_b = [0.0] * w

    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            r = max(0.0, min(255.0, r + err_r[x]))
            g = max(0.0, min(255.0, g + err_g[x]))
            b = max(0.0, min(255.0, b + err_b[x]))

            idx, pr, pg, pb = nearest_seven_color(r, g, b)

            # 写回量化后的颜色
            pixels[x, y] = (pr, pg, pb)

            # 误差
            er = r - pr
            eg = g - pg
            eb = b - pb

            # Floyd–Steinberg:
            #        *   7/16
            #   3/16 5/16 1/16
            if x + 1 < w:
                err_r[x + 1] += er * (7.0 / 16.0)
                err_g[x + 1] += eg * (7.0 / 16.0)
                err_b[x + 1] += eb * (7.0 / 16.0)
            if y + 1 < h:
                if x > 0:
                    next_err_r[x - 1] += er * (3.0 / 16.0)
                    next_err_g[x - 1] += eg * (3.0 / 16.0)
                    next_err_b[x - 1] += eb * (3.0 / 16.0)
                next_err_r[x] += er * (5.0 / 16.0)
                next_err_g[x] += eg * (5.0 / 16.0)
                next_err_b[x] += eb * (5.0 / 16.0)
                if x + 1 < w:
                    next_err_r[x + 1] += er * (1.0 / 16.0)
                    next_err_g[x + 1] += eg * (1.0 / 16.0)
                    next_err_b[x + 1] += eb * (1.0 / 16.0)

        if y + 1 < h:
            # 把 next_err_* 移到当前行，并清零 next_err_*
            for i in range(w):
                err_r[i] = next_err_r[i]
                err_g[i] = next_err_g[i]
                err_b[i] = next_err_b[i]
                next_err_r[i] = 0.0
                next_err_g[i] = 0.0
                next_err_b[i] = 0.0

    return img


def color_index_to_black_color(idx: int) -> Tuple[int, int]:
    """
    将 7 色索引转换为 (black, color) 两层。

    根据 GxEPD2 库的实现：
    - black 层：0=黑色, 1=白色
    - color 层：0-6 表示不同的颜色组合

    映射规则：
    - 0 (黑) → black=1, color=0
    - 1 (白) → black=0, color=0
    - 2 (红) → black=0, color=2
    - 3 (黄) → black=0, color=3
    - 4 (橙) → black=0, color=4
    - 5 (蓝) → black=0, color=5
    - 6 (绿) → black=0, color=6

    注意：这是简化的映射，实际需要根据屏幕规格调整。
    """
    if idx == 0:  # 黑色
        return (1, 0)
    elif idx == 1:  # 白色
        return (0, 0)
    else:  # 其他颜色
        return (0, idx)


def image_to_7color_bin(img: Image.Image) -> bytes:
    """
    把已经量化到 SEVEN_COLOR_PALETTE 的图像转换成 2 层 BIN：
    - 行优先，从上到下，从左到右
    - 文件结构：先 black 层（480×800 字节），再 color 层（480×800 字节）
    - 总大小：768,000 字节（768KB）
    """
    img = img.convert("RGB")
    w, h = img.size
    if (w, h) != (480, 800):
        raise RuntimeError(f"图像尺寸错误：{(w, h)}，应为 (480, 800)")

    black_layer = bytearray(w * h)
    color_layer = bytearray(w * h)

    # 建立 RGB → 索引的映射
    idx_map = {c: i for i, c in enumerate(SEVEN_COLOR_PALETTE)}

    for y in range(h):
        for x in range(w):
            r, g, b = img.getpixel((x, y))
            idx = idx_map.get((r, g, b), 1)  # 默认白色

            # 分解为 black 和 color 两层
            black_val, color_val = color_index_to_black_color(idx)
            black_layer[y * w + x] = black_val
            color_layer[y * w + x] = color_val

    # 组合：先 black 层，再 color 层
    return bytes(black_layer) + bytes(color_layer)


def create_test_image() -> Image.Image:
    """
    创建一个测试图像，包含所有 7 种颜色和渐变。
    """
    img = Image.new("RGB", (480, 800), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 绘制 7 个色块（垂直排列）
    colors = SEVEN_COLOR_PALETTE
    block_height = 800 // 7

    for i, color in enumerate(colors):
        y0 = i * block_height
        y1 = y0 + block_height
        draw.rectangle([0, y0, 480, y1], fill=color)

        # 在色块中间绘制文字
        text = f"Color {i}: {color}"
        # 简单绘制（不使用字体，避免依赖）
        draw.text((10, y0 + 10), text, fill=(255, 255, 255) if i > 0 else (0, 0, 0))

    return img


def main():
    """
    主函数：测试 7 色渲染流程。
    """
    print("7 色墨水屏渲染测试")
    print("=" * 50)

    # 1. 创建测试图像
    print("\n1. 创建测试图像...")
    test_img = create_test_image()
    test_img.save("/Users/allen/Documents/Jedi/InkTime/test/test_7color_source.png")
    print("   ✅ 源图像保存到: test/test_7color_source.png")

    # 2. 应用 7 色 Dither
    print("\n2. 应用 7 色 Floyd-Steinberg Dither...")
    dithered = apply_seven_color_dither(test_img)
    dithered.save("/Users/allen/Documents/Jedi/InkTime/test/test_7color_dithered.png")
    print("   ✅ 抖动后图像保存到: test/test_7color_dithered.png")

    # 3. 生成 2 层 BIN 文件
    print("\n3. 生成 2 层 BIN 文件...")
    bin_data = image_to_7color_bin(dithered)
    bin_path = Path("/Users/allen/Documents/Jedi/InkTime/test/test_7color.bin")
    bin_path.write_bytes(bin_data)
    print(f"   ✅ BIN 文件保存到: {bin_path}")
    print(f"   文件大小: {len(bin_data):,} 字节 ({len(bin_data) / 1024:.1f} KB)")

    # 4. 验证数据
    print("\n4. 验证数据...")
    expected_size = 480 * 800 * 2  # 2 层
    if len(bin_data) == expected_size:
        print(f"   ✅ BIN 文件大小正确: {expected_size:,} 字节")
    else:
        print(f"   ❌ BIN 文件大小错误: 期望 {expected_size:,}，实际 {len(bin_data):,}")

    print("\n" + "=" * 50)
    print("测试完成！")


if __name__ == "__main__":
    main()
