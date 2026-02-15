"""Raster image -> PNG conversion via Pillow.

Handles the bit-flip and PBM->PNG conversion from the Scheme code.
"""

import base64
import io


def _flip_byte(n: int) -> int:
    """Reverse bits in a byte (MSB<->LSB), per Scheme flip-byte."""
    result = 0
    for i in range(8):
        if n & (1 << i):
            result |= (1 << (7 - i))
    return result


# Pre-compute flip table for speed
_FLIP_TABLE = bytes(_flip_byte(i) for i in range(256))


def raster_to_png_bytes(raster_image) -> bytes:
    """Convert an OpRasterImage to PNG bytes using Pillow."""
    from PIL import Image

    width = raster_image.width
    height = raster_image.height
    data = raster_image.data

    # Flip all bytes (MSB<->LSB reversal)
    flipped = data.translate(_FLIP_TABLE)

    # Create a 1-bit image from the PBM data
    img = Image.frombytes('1', (width, height), flipped, 'raw', '1', 0, 1)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def raster_to_png_data_uri(raster_image) -> str:
    """Convert an OpRasterImage to a base64 data URI."""
    png_bytes = raster_to_png_bytes(raster_image)
    b64 = base64.b64encode(png_bytes).decode('ascii')
    return f"data:image/png;base64,{b64}"
