"""Binary graphics sub-format parser.

Ports the Scheme binary-graphics.lisp format reader.
Two dispatch tables: commands (produce values) and operations (produce shapes).
"""

import struct
from dataclasses import dataclass, field
from typing import Any
from .stream import SabStream

# Dispatch tables
_command_opcodes = [None] * 256
_operation_opcodes = [None] * 256

# Keyword table for graphics options (95 entries)
BINARY_GRAPHICS_KEYWORDS = [
    ':bevel', ':butt', ':miter', ':none', ':round', ':square',
    ':draw', ':erase', ':flip',
    ':baseline', ':bottom', ':center', ':left', ':right', ':top',
    ':anti-cyclic', ':clamped', ':cyclic', ':relaxed',
    ':non-zero', ':odd-even',
    ':alu', ':attachment-x', ':attachment-y', ':character-style',
    ':clockwise', ':closed', ':copy-image',
    ':dash-pattern', ':scale-dashes', ':dashed', ':draw-end-point',
    ':draw-partial-dashes', ':end-angle',
    ':end-relaxation', ':end-slope-dx', ':end-slope-dy', ':filled',
    ':gray-level', ':handedness', ':image-bottom',
    ':image-left', ':image-right', ':image-top', ':initial-dash-phase',
    ':inner-x-radius', ':inner-y-radius',
    ':join-to-path', ':line-end-shape', ':line-joint-shape', ':mask',
    ':new-value', ':number-of-samples', ':opaque',
    ':pattern', ':points-are-convex-p', ':start-angle',
    ':start-relaxation', ':start-slope-dx', ':start-slope-dy',
    ':stretch-p', ':thickness', ':toward-x', ':toward-y', ':winding-rule',
    ':scale-thickness', ':character-size', ':string-width',
    ':scale-down-allowed', ':mask-x', ':mask-y',
    ':color', ':stipple', ':tile', ':shape', ':record-as-text',
    ':scan-conversion-mode',
    ':round-coordinates', ':center-circles', ':host-allowed', ':sketch',
    ':flatness',
    ':object', ':type', ':single-box', ':allow-sensitive-inferiors',
]

FORMAT_VERSION = 1

# Sentinel value for %com-end
_END_VALUE = object()


# ========== Data structures for graphics operations ==========

@dataclass
class OpPoint:
    x: Any
    y: Any
    options: list

@dataclass
class OpLine:
    start_x: Any
    start_y: Any
    end_x: Any
    end_y: Any
    options: list

@dataclass
class OpLines:
    points: list  # flat list of x,y coords
    options: list

@dataclass
class OpRectangle:
    left: Any
    top: Any
    right: Any
    bottom: Any
    options: list

@dataclass
class OpTriangle:
    x1: Any
    y1: Any
    x2: Any
    y2: Any
    x3: Any
    y3: Any
    options: list

@dataclass
class OpPolygon:
    points: list
    options: list

@dataclass
class OpEllipse:
    center_x: Any
    center_y: Any
    radius_x: Any
    radius_y: Any
    options: list

@dataclass
class OpBezierCurve:
    start_x: Any
    start_y: Any
    end_x: Any
    end_y: Any
    control_1_x: Any
    control_1_y: Any
    control_2_x: Any
    control_2_y: Any
    options: list

@dataclass
class OpCubicSpline:
    points: list
    options: list

@dataclass
class OpPath:
    path_function: Any
    options: list

@dataclass
class OpString:
    string: str
    x: Any
    y: Any
    options: list

@dataclass
class OpStringImage:
    string: str
    x: Any
    y: Any
    options: list

@dataclass
class OpCircularArcTo:
    to_x: Any
    to_y: Any
    tangent_intersection_x: Any
    tangent_intersection_y: Any
    radius: Any
    options: list

@dataclass
class OpImage:
    image: Any
    left: Any
    top: Any
    options: list

@dataclass
class OpLineTo:
    end_x: Any
    end_y: Any
    options: list

@dataclass
class OpClosePath:
    options: list

@dataclass
class OpSetCurrentPosition:
    x: Any
    y: Any
    options: list

@dataclass
class OpGraphicsTransform:
    r11: Any
    r12: Any
    r21: Any
    r22: Any
    tx: Any
    ty: Any

@dataclass
class OpScanConversionMode:
    output_forms: list
    options: list

@dataclass
class OpRasterImage:
    byte_size: int
    width: int
    height: int
    data: bytes


# ========== Helper functions ==========

def _next_value(stream: SabStream):
    """Read commands until one produces a value."""
    while True:
        byte = stream.read_u8()
        command = _command_opcodes[byte]
        if command:
            result, has_value = command(stream)
            if has_value:
                return result
            # else loop - command was for effect only
        else:
            raise ValueError(
                f"Unknown binary graphics opcode {byte} at 0x{stream.offset - 1:x}"
            )


def _read_until_done(stream: SabStream) -> list:
    """Read values until we get the end marker."""
    result = []
    while True:
        val = _next_value(stream)
        if val is _END_VALUE:
            return result
        result.append(val)


def binary_decode_graphics(data: bytes) -> list:
    """Decode binary graphics data into a list of operations/forms."""
    stream = SabStream(data, 0)
    return _decode_graphics_into_forms(stream)


def _decode_graphics_into_forms(stream: SabStream) -> list:
    """Read the full graphics stream into a list of operations."""
    forms = []
    while not stream.eof():
        byte = stream.read_u8()

        # Try command first
        command = _command_opcodes[byte]
        if command:
            result, result_type = command(stream)
            if result_type is True:
                # for-value at top level
                if result is _END_VALUE:
                    return forms
                raise ValueError(f"for-value command at top-level: {result}")
            elif result_type is False:
                # for-effect, continue
                pass
            elif result_type == ':form':
                forms.append(result)
            else:
                raise ValueError(f"Unknown result type: {result_type}")
            continue

        # Try operation
        operation = _operation_opcodes[byte]
        if operation:
            result = operation(stream)
            forms.append(result)
            continue

        raise ValueError(
            f"Garbage byte {byte} in graphics input at 0x{stream.offset - 1:x}"
        )

    return forms


# ========== Command implementations ==========

def _register_command(opcode, func):
    _command_opcodes[opcode] = func

def _register_operation(opcode, func):
    _operation_opcodes[opcode] = func


# %com-end (50) - signals end of sequence
def _com_end(stream):
    return (_END_VALUE, True)
_register_command(50, _com_end)


# %com-format-version (51) - verify format version
def _com_format_version(stream):
    version = stream.read_u8()
    if version != FORMAT_VERSION:
        raise ValueError(f"Bad graphics format version {version}, expected {FORMAT_VERSION}")
    return (None, False)
_register_command(51, _com_format_version)


# %com-small-integer (52) - 1-byte integer, biased by -128
def _com_small_integer(stream):
    return (stream.read_u8() - 128, True)
_register_command(52, _com_small_integer)


# %com-medium-integer (53) - 2-byte integer, biased by -32768
def _com_medium_integer(stream):
    low = stream.read_u8()
    high = stream.read_u8()
    return (low + high * 256 - 32768, True)
_register_command(53, _com_medium_integer)


# %op-large-integer (54) - 4-byte integer
def _com_large_integer(stream):
    val = stream.read_u32_le()
    return (val, True)
_register_command(54, _com_large_integer)


# %op-very-large-integer (55) - variable length integer
def _com_very_large_integer(stream):
    length0 = stream.read_u8()
    length1 = stream.read_u8()
    length = length0 + (length1 << 8)
    n = (length + 7) // 8
    number = 0
    for i in range(n):
        number += stream.read_u8() << (i * 8)
    return (number, True)
_register_command(55, _com_very_large_integer)


# %com-ratio (56) - rational number
def _com_ratio(stream):
    num = _next_value(stream)
    denom = _next_value(stream)
    return (num / denom, True)
_register_command(56, _com_ratio)


# %com-single-float (57) - IEEE 754 single
def _com_single_float(stream):
    val, = struct.unpack_from('<f', stream.data, stream.offset)
    stream.offset += 4
    return (val, True)
_register_command(57, _com_single_float)


# %com-double-float (58) - IEEE 754 double
def _com_double_float(stream):
    val, = struct.unpack_from('<d', stream.data, stream.offset)
    stream.offset += 8
    return (val, True)
_register_command(58, _com_double_float)


# %com-point-sequence (59) - vector of coordinate pairs
def _com_point_sequence(stream):
    length = _next_value(stream)
    points = []
    for _ in range(length * 2):
        p = _next_value(stream)
        points.append(p)
    return (points, True)
_register_command(59, _com_point_sequence)


# %com-angle (60) - angle in tenths of degrees -> radians
def _com_angle(stream):
    import math
    tenths = _next_value(stream)
    radians = (tenths * 2 * math.pi) / 3600.0
    return (radians, True)
_register_command(60, _com_angle)


# %com-true (62)
def _com_true(stream):
    return (True, True)
_register_command(62, _com_true)


# %com-false (63)
def _com_false(stream):
    return (False, True)
_register_command(63, _com_false)


# %com-keyword (64) - index into keyword table
def _com_keyword(stream):
    index = stream.read_u8()
    return (BINARY_GRAPHICS_KEYWORDS[index], True)
_register_command(64, _com_keyword)


# %com-set-position (67) - set current position (produces a form)
def _com_set_position(stream):
    x = _next_value(stream)
    y = _next_value(stream)
    return (OpSetCurrentPosition(x=x, y=y, options=[]), ':form')
_register_command(67, _com_set_position)


# %com-transform-matrix (68) - affine transform (produces a form)
def _com_transform_matrix(stream):
    r11 = _next_value(stream)
    r12 = _next_value(stream)
    r21 = _next_value(stream)
    r22 = _next_value(stream)
    tx = _next_value(stream)
    ty = _next_value(stream)
    return (OpGraphicsTransform(r11=r11, r12=r12, r21=r21, r22=r22, tx=tx, ty=ty), ':form')
_register_command(68, _com_transform_matrix)


# %com-thin-string (20) - string value
def _com_thin_string(stream):
    length = stream.read_u8()
    s = stream.read_bytes(length).decode('latin-1')
    return (s, True)
_register_command(20, _com_thin_string)


# %com-path (22) - recursive graphics decode
def _com_path(stream):
    forms = _decode_graphics_into_forms(stream)
    return (forms, True)
_register_command(22, _com_path)


# %com-raster-image (23) - inline raster image
def _com_raster_image(stream):
    byte_size = stream.read_u8()
    width = _next_value(stream)
    height = _next_value(stream)
    byte_length = (width * byte_size // 8) * height
    data = stream.read_bytes(byte_length)
    return (OpRasterImage(byte_size=byte_size, width=width, height=height, data=data), True)
_register_command(23, _com_raster_image)


# %com-character-style (24) - character style name
def _com_character_style(stream):
    length = stream.read_u8()
    s = stream.read_bytes(length).decode('latin-1')
    return (s, True)
_register_command(24, _com_character_style)


# %op-dash-pattern (72) - dash pattern list
def _com_dash_pattern(stream):
    length = _next_value(stream)
    pattern = [_next_value(stream) for _ in range(length)]
    return (pattern, True)
_register_command(72, _com_dash_pattern)


# %op-scan-conversion-mode (74) - contains sub-forms
def _com_scan_conversion_mode(stream):
    output_forms = _decode_graphics_into_forms(stream)
    options = _read_until_done(stream)
    return (OpScanConversionMode(output_forms=output_forms, options=options), ':form')
_register_command(74, _com_scan_conversion_mode)


# ========== Operation implementations ==========

# %op-point (1)
def _op_point(stream):
    x = _next_value(stream)
    y = _next_value(stream)
    return OpPoint(x=x, y=y, options=_read_until_done(stream))
_register_operation(1, _op_point)


# %op-line (2)
def _op_line(stream):
    sx = _next_value(stream)
    sy = _next_value(stream)
    ex = _next_value(stream)
    ey = _next_value(stream)
    return OpLine(start_x=sx, start_y=sy, end_x=ex, end_y=ey, options=_read_until_done(stream))
_register_operation(2, _op_line)


# %op-lines (3)
def _op_lines(stream):
    points = _next_value(stream)
    return OpLines(points=points, options=_read_until_done(stream))
_register_operation(3, _op_lines)


# %op-rectangle (4)
def _op_rectangle(stream):
    left = _next_value(stream)
    top = _next_value(stream)
    right = _next_value(stream)
    bottom = _next_value(stream)
    return OpRectangle(left=left, top=top, right=right, bottom=bottom, options=_read_until_done(stream))
_register_operation(4, _op_rectangle)


# %op-triangle (5)
def _op_triangle(stream):
    x1 = _next_value(stream)
    y1 = _next_value(stream)
    x2 = _next_value(stream)
    y2 = _next_value(stream)
    x3 = _next_value(stream)
    y3 = _next_value(stream)
    return OpTriangle(x1=x1, y1=y1, x2=x2, y2=y2, x3=x3, y3=y3, options=_read_until_done(stream))
_register_operation(5, _op_triangle)


# %op-polygon (6)
def _op_polygon(stream):
    points = _next_value(stream)
    return OpPolygon(points=points, options=_read_until_done(stream))
_register_operation(6, _op_polygon)


# %op-ellipse (8)
def _op_ellipse(stream):
    cx = _next_value(stream)
    cy = _next_value(stream)
    rx = _next_value(stream)
    ry = _next_value(stream)
    return OpEllipse(center_x=cx, center_y=cy, radius_x=rx, radius_y=ry, options=_read_until_done(stream))
_register_operation(8, _op_ellipse)


# %op-bezier-curve (9)
def _op_bezier_curve(stream):
    sx = _next_value(stream)
    sy = _next_value(stream)
    ex = _next_value(stream)
    ey = _next_value(stream)
    c1x = _next_value(stream)
    c1y = _next_value(stream)
    c2x = _next_value(stream)
    c2y = _next_value(stream)
    return OpBezierCurve(start_x=sx, start_y=sy, end_x=ex, end_y=ey,
                         control_1_x=c1x, control_1_y=c1y,
                         control_2_x=c2x, control_2_y=c2y,
                         options=_read_until_done(stream))
_register_operation(9, _op_bezier_curve)


# %op-cubic-spline (10)
def _op_cubic_spline(stream):
    points = _next_value(stream)
    return OpCubicSpline(points=points, options=_read_until_done(stream))
_register_operation(10, _op_cubic_spline)


# %op-path (11)
def _op_path(stream):
    path_function = _next_value(stream)
    return OpPath(path_function=path_function, options=_read_until_done(stream))
_register_operation(11, _op_path)


# %op-string (12)
def _op_string(stream):
    s = _next_value(stream)
    x = _next_value(stream)
    y = _next_value(stream)
    return OpString(string=s, x=x, y=y, options=_read_until_done(stream))
_register_operation(12, _op_string)


# %op-circular-arc-to (14)
def _op_circular_arc_to(stream):
    to_x = _next_value(stream)
    to_y = _next_value(stream)
    tix = _next_value(stream)
    tiy = _next_value(stream)
    radius = _next_value(stream)
    return OpCircularArcTo(to_x=to_x, to_y=to_y,
                           tangent_intersection_x=tix,
                           tangent_intersection_y=tiy,
                           radius=radius,
                           options=_read_until_done(stream))
_register_operation(14, _op_circular_arc_to)


# %op-image (16)
def _op_image(stream):
    image = _next_value(stream)
    left = _next_value(stream)
    top = _next_value(stream)
    return OpImage(image=image, left=left, top=top, options=_read_until_done(stream))
_register_operation(16, _op_image)


# %op-string-image (17)
def _op_string_image(stream):
    s = _next_value(stream)
    x = _next_value(stream)
    y = _next_value(stream)
    return OpStringImage(string=s, x=x, y=y, options=_read_until_done(stream))
_register_operation(17, _op_string_image)


# %op-line-to (18)
def _op_line_to(stream):
    ex = _next_value(stream)
    ey = _next_value(stream)
    return OpLineTo(end_x=ex, end_y=ey, options=_read_until_done(stream))
_register_operation(18, _op_line_to)


# %op-close-path (19)
def _op_close_path(stream):
    return OpClosePath(options=_read_until_done(stream))
_register_operation(19, _op_close_path)
