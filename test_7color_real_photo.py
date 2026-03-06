#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
7 色渲染真实照片测试
- 从 photos.db 选一张高分照片
- 应用 InkTime 布局
- 使用 7 色 Dither 渲染
- 生成预览和 BIN 文件
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
import json
import datetime as dt
from typing import List, Dict, Any
from PIL import Image, ImageDraw, ImageFont
import sys

# 导入 7 色渲染模块
from render_7color import (
    SEVEN_COLOR_PALETTE,
    nearest_seven_color,
    apply_seven_color_dither,
    image_to_7color_bin
)

# 导入配置
import config as cfg

# 路径配置
ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = Path(str(getattr(cfg, "DB_PATH", "photos.db") or "photos.db")).expanduser()
if not DB_PATH.is_absolute():
    DB_PATH = (ROOT_DIR / DB_PATH).resolve()

FONT_PATH = Path(str(getattr(cfg, "FONT_PATH", "") or "")).expanduser()
if str(FONT_PATH) and not FONT_PATH.is_absolute():
    FONT_PATH = (ROOT_DIR / FONT_PATH).resolve()

# 墨水屏尺寸
CANVAS_WIDTH = 480
CANVAS_HEIGHT = 800

# 底部文字区域高度
TEXT_AREA_HEIGHT = 100


def extract_date_from_exif(exif_json: str) -> str:
    """从 EXIF JSON 中提取拍摄日期"""
    if not exif_json:
        return dt.datetime.now().strftime("%Y-%m-%d")
    try:
        data = json.loads(exif_json)
        dt_str = data.get("datetime")
        if dt_str:
            date_part = str(dt_str).split()[0]
            parts = date_part.replace(":", "-").split("-")
            if len(parts) >= 3:
                return f"{parts[0]}-{parts[1]}-{parts[2]}"
    except Exception:
        pass
    return dt.datetime.now().strftime("%Y-%m-%d")


def load_random_photo() -> Dict[str, Any]:
    """从数据库加载一张随机高分照片"""
    if not DB_PATH.exists():
        raise SystemExit(f"找不到数据库: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 选择回忆度 > 80 的照片
    rows = c.execute("""
        SELECT
            path, exif_json, side_caption, memory_score,
            exif_gps_lat, exif_gps_lon, exif_city
        FROM photo_scores
        WHERE memory_score > 80
        ORDER BY RANDOM()
        LIMIT 1
    """).fetchall()

    conn.close()

    if not rows:
        raise SystemExit("没有找到高分照片（memory > 80）")

    row = rows[0]
    return {
        "path": row[0],
        "exif_json": row[1],
        "caption": row[2],
        "memory": row[3],
        "lat": row[4],
        "lon": row[5],
        "city": row[6],
    }


def render_inktime_layout(photo_path: str, caption: str, date_str: str, location: str) -> Image.Image:
    """
    按 InkTime 布局渲染照片到 480x800
    - 上部：照片区域（600×800，居中裁剪到 480×700）
    - 下部：文字区域（480×100）
    """
    # 1. 加载照片
    photo = Image.open(photo_path)

    # 2. 居中裁剪到 480×700（保持比例）
    photo_width, photo_height = photo.size

    # 计算裁剪区域（居中）
    target_ratio = 480 / 700
    photo_ratio = photo_width / photo_height

    if photo_ratio > target_ratio:
        # 照片更宽，裁剪左右
        new_height = 700
        new_width = int(new_height * photo_ratio)
        photo_resized = photo.resize((new_width, new_height), Image.Resampling.LANCZOS)
        x_offset = (new_width - 480) // 2
        photo_cropped = photo_resized.crop((x_offset, 0, x_offset + 480, 700))
    else:
        # 照片更高，裁剪上下
        new_width = 480
        new_height = int(new_width / photo_ratio)
        photo_resized = photo.resize((new_width, new_height), Image.Resampling.LANCZOS)
        y_offset = (new_height - 700) // 2
        photo_cropped = photo_resized.crop((0, y_offset, 480, y_offset + 700))

    # 3. 创建画布（480×800）
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (255, 255, 255))
    canvas.paste(photo_cropped, (0, 0))

    # 4. 绘制文字区域
    draw = ImageDraw.Draw(canvas)

    # 加载字体
    try:
        font_large = ImageFont.truetype(str(FONT_PATH), 32)
        font_small = ImageFont.truetype(str(FONT_PATH), 24)
    except Exception as e:
        print(f"字体加载失败: {e}")
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # 绘制分割线
    draw.line([(10, 700), (470, 700)], fill=(0, 0, 0), width=2)

    # 绘制日期（左上）
    draw.text((20, 710), date_str, fill=(0, 0, 0), font=font_small)

    # 绘制地点（右上）
    if location:
        draw.text((470 - draw.textlength(location, font=font_small), 710),
                  location, fill=(0, 0, 0), font=font_small)

    # 绘制文案（居中）
    if caption:
        # 简单折行（最多 2 行）
        lines = []
        line = ""
        for ch in caption:
            test = line + ch
            if draw.textlength(test, font=font_large) <= 440:
                line = test
            else:
                if line:
                    lines.append(line)
                line = ch
                if len(lines) >= 2:
                    break
        if line:
            lines.append(line)

        # 绘制每一行
        y_offset = 745
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_large)
            text_width = bbox[2] - bbox[0]
            x = (480 - text_width) // 2
            draw.text((x, y_offset), line, fill=(0, 0, 0), font=font_large)
            y_offset += 35

    return canvas


def format_date_display(date_str: str) -> str:
    """YYYY-MM-DD -> YYYY.M.D"""
    if not date_str:
        return ""
    parts = date_str.split("-")
    if len(parts) < 3:
        return date_str
    return f"{parts[0]}.{int(parts[1])}.{int(parts[2])}"


def format_location(lat, lon, city: str) -> str:
    """地点字符串"""
    if city:
        return city
    if lat is not None and lon is not None:
        return f"{lat:.5f}, {lon:.5f}"
    return ""


def main():
    """主测试流程"""
    print("=" * 60)
    print("7 色墨水屏真实照片测试")
    print("=" * 60)

    # 1. 加载照片信息
    print("\n1. 从数据库加载高分照片...")
    photo_info = load_random_photo()
    print(f"   ✅ 照片: {photo_info['path']}")
    print(f"   回忆度: {photo_info['memory']:.1f}")
    print(f"   文案: {photo_info['caption'][:30] if photo_info['caption'] else '(无)'}...")

    # 2. 提取元数据
    date_str = extract_date_from_exif(photo_info['exif_json'])
    formatted_date = format_date_display(date_str)
    location = format_location(
        photo_info.get('lat'),
        photo_info.get('lon'),
        photo_info.get('city') or ''
    )

    print(f"   日期: {formatted_date}")
    print(f"   地点: {location if location else '(未知)'}")

    # 3. 渲染 InkTime 布局
    print("\n2. 渲染 InkTime 布局...")
    try:
        canvas = render_inktime_layout(
            photo_info['path'],
            photo_info['caption'] or "",
            formatted_date,
            location
        )
        print("   ✅ 布局渲染成功")
    except Exception as e:
        print(f"   ❌ 布局渲染失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. 保存原始渲染图
    output_dir = ROOT_DIR / "output/inktime"
    output_dir.mkdir(parents=True, exist_ok=True)

    source_path = output_dir / "7color_test_source.png"
    canvas.save(source_path)
    print(f"   ✅ 源图像保存到: {source_path}")

    # 5. 应用 7 色 Dither
    print("\n3. 应用 7 色 Floyd-Steinberg Dither...")
    try:
        dithered = apply_seven_color_dither(canvas)
        print("   ✅ 抖动完成")
    except Exception as e:
        print(f"   ❌ 抖动失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 6. 保存抖动后图像
    dithered_path = output_dir / "7color_test_dithered.png"
    dithered.save(dithered_path)
    print(f"   ✅ 抖动图像保存到: {dithered_path}")

    # 7. 生成 BIN 文件
    print("\n4. 生成 2 层 BIN 文件...")
    try:
        bin_data = image_to_7color_bin(dithered)
        print(f"   ✅ BIN 文件生成成功 ({len(bin_data):,} 字节)")
    except Exception as e:
        print(f"   ❌ BIN 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 8. 保存 BIN 文件
    bin_path = output_dir / "7color_test.bin"
    bin_path.write_bytes(bin_data)
    print(f"   ✅ BIN 文件保存到: {bin_path}")

    # 9. 生成对比图
    print("\n5. 生成对比图...")
    try:
        # 创建并排对比图
        comparison = Image.new("RGB", (960, 800))
        comparison.paste(canvas, (0, 0))
        comparison.paste(dithered, (480, 0))

        # 添加标签
        draw = ImageDraw.Draw(comparison)
        try:
            font_label = ImageFont.truetype(str(FONT_PATH), 20)
        except Exception:
            font_label = ImageFont.load_default()

        draw.text((10, 10), "Original", fill=(255, 0, 0), font=font_label)
        draw.text((490, 10), "7-Color Dither", fill=(255, 0, 0), font=font_label)

        comparison_path = output_dir / "7color_test_comparison.png"
        comparison.save(comparison_path)
        print(f"   ✅ 对比图保存到: {comparison_path}")
    except Exception as e:
        print(f"   ⚠️  对比图生成失败: {e}")

    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)
    print(f"\n生成的文件:")
    print(f"  - 源图像: {source_path}")
    print(f"  - 抖动图: {dithered_path}")
    print(f"  - 对比图: {comparison_path}")
    print(f"  - BIN 文件: {bin_path}")


if __name__ == "__main__":
    main()
