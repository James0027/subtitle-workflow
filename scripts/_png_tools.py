"""纯标准库 PNG 裁剪/尺寸工具（不引入 Pillow 等依赖）。

用途：Chrome ``--headless --screenshot`` 只能按窗口尺寸出图，底部常留大片空白；
本模块解码 PNG、从底部向上找最后一行“有内容”的扫描线，裁掉纯空白区并重编码。

支持：8 bit、非隔行、颜色类型 2(RGB) / 6(RGBA) / 0(灰度)。其余类型原样返回不裁剪。
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_png(path: Path) -> tuple[int, int, int, bytearray]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIG):
        raise ValueError("不是 PNG")
    pos = len(PNG_SIG)
    width = height = bit_depth = color_type = 0
    idat = bytearray()
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(">IIBBBBB", chunk)
            if bit_depth != 8 or interlace != 0 or comp != 0 or filt != 0:
                raise ValueError(f"不支持的 PNG 编码 bit={bit_depth} interlace={interlace}")
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
    channels = {0: 1, 2: 3, 6: 4}.get(color_type)
    if channels is None:
        raise ValueError(f"不支持的 PNG 颜色类型 {color_type}")
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(stride * height)
    prev = bytearray(stride)
    offset = 0
    for row in range(height):
        ftype = raw[offset]
        offset += 1
        line = bytearray(raw[offset:offset + stride])
        offset += stride
        if ftype == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up_left = prev[i - channels] if i >= channels else 0
                line[i] = (line[i] + _paeth(left, prev[i], up_left)) & 0xFF
        elif ftype != 0:
            raise ValueError(f"未知 PNG 行过滤类型 {ftype}")
        out[row * stride:(row + 1) * stride] = line
        prev = line
    return width, height, channels, out


def write_png(path: Path, width: int, height: int, channels: int, pixels: bytearray) -> None:
    color_type = {1: 0, 3: 2, 4: 6}[channels]
    stride = width * channels
    raw = bytearray()
    for row in range(height):
        raw.append(0)
        raw += pixels[row * stride:(row + 1) * stride]

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    path.write_bytes(
        PNG_SIG
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


def content_bottom(height: int, width: int, channels: int, pixels: bytearray) -> int:
    """返回最后一个“非页面背景行”的下一行索引（即内容底边）。

    背景色取图像左上角像素；只有与背景同色的整行才视为可裁空白，
    这样句末的深色代码块/日志块不会被误裁。
    """
    stride = width * channels
    bg = bytes(pixels[0:channels]) * width
    for row in range(height - 1, -1, -1):
        line = pixels[row * stride:(row + 1) * stride]
        if bytes(line) != bg:
            return row + 1
    return 1


def crop_bottom(path: Path, padding: int = 26, min_height: int = 200) -> dict:
    width, height, channels, pixels = read_png(path)
    bottom = content_bottom(height, width, channels, pixels)
    new_height = max(min_height, min(height, bottom + padding))
    if new_height >= height:
        return {"cropped": False, "width": width, "height": height}
    stride = width * channels
    cropped = pixels[: new_height * stride]
    write_png(path, width, new_height, channels, bytearray(cropped))
    return {"cropped": True, "from_height": height, "to_height": new_height, "width": width}


if __name__ == "__main__":
    import sys

    for argument in sys.argv[1:]:
        print(argument, crop_bottom(Path(argument)))
