"""Graphics operations -> SVG strings.

Ports the Scheme picture-ops->sxml and related SVG generation code.
"""

from .binary_graphics import (
    OpPoint, OpLine, OpLines, OpRectangle, OpTriangle, OpPolygon,
    OpEllipse, OpBezierCurve, OpCubicSpline, OpPath, OpString,
    OpStringImage, OpCircularArcTo, OpImage, OpLineTo, OpClosePath,
    OpSetCurrentPosition, OpGraphicsTransform, OpScanConversionMode,
    OpRasterImage,
)
from .png_writer import raster_to_png_data_uri
import re
from xml.sax.saxutils import escape as _xml_escape

_ILLEGAL_XML_CHARS = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]')

def xml_escape(text: str) -> str:
    return _xml_escape(_ILLEGAL_XML_CHARS.sub('\ufffd', text))


def _fmt(n):
    """Format a number for SVG output."""
    f = float(n)
    r = round(f * 1000) / 1000.0
    s = f"{r:.3f}".rstrip('0')
    if s.endswith('.'):
        s += '0'
    return s


def _plist_get(options, key, default=None):
    """Get a value from a plist-style options list (alternating keys and values)."""
    for i in range(0, len(options) - 1, 2):
        if options[i] == key:
            return options[i + 1]
    return default


class BoundingBox:
    __slots__ = ('x1', 'y1', 'x2', 'y2')

    def __init__(self, x1=0, y1=0, x2=0, y2=0):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    def extend_point(self, x, y):
        self.x1 = min(self.x1, x)
        self.y1 = min(self.y1, y)
        self.x2 = max(self.x2, x)
        self.y2 = max(self.y2, y)

    def extend_box(self, other):
        self.x1 = min(self.x1, other.x1)
        self.y1 = min(self.y1, other.y1)
        self.x2 = max(self.x2, other.x2)
        self.y2 = max(self.y2, other.y2)


def _gray_to_rgb(gray_level):
    """Convert gray level (0=black, 1=white) to CSS rgb string."""
    v = round(255 * (1 - gray_level))
    return f"rgb({v},{v},{v})"


def _points_to_string(points, invert_y=False):
    """Convert a flat list of x,y coordinates to SVG points string."""
    pairs = []
    for i in range(0, len(points), 2):
        x = points[i]
        y = -points[i + 1] if invert_y else points[i + 1]
        pairs.append(f"{_fmt(x)},{_fmt(y)}")
    return " ".join(pairs)


def _points_to_cubic(points, invert_y=False):
    """Convert points to an SVG cubic/quadratic bezier path."""
    pairs = []
    for i in range(0, len(points), 2):
        x = points[i]
        y = -points[i + 1] if invert_y else points[i + 1]
        pairs.append(f"{_fmt(x)},{_fmt(y)}")

    if len(pairs) < 2:
        return ""

    path = f"M {pairs[0]}"
    rest = pairs[1:]
    if len(rest) == 3:
        path += f" C {' '.join(rest)}"
    else:
        path += f" Q {' '.join(rest)}"
    return path


def _path_to_svg(path_ops):
    """Convert path operations to SVG path d attribute."""
    parts = []
    for el in path_ops:
        if isinstance(el, OpClosePath):
            parts.append("Z")
        elif isinstance(el, OpLineTo):
            parts.append(f"l{_fmt(el.end_x)},{_fmt(-el.end_y)}")
        elif isinstance(el, OpSetCurrentPosition):
            parts.append(f"M{_fmt(el.x)},{_fmt(-el.y)}")
        elif isinstance(el, OpCircularArcTo):
            parts.append(f"L{_fmt(el.to_x)} {_fmt(-el.to_y)}")
        elif isinstance(el, OpLines):
            parts.append(f"L{_points_to_string(el.points)}")
        else:
            pass  # skip unknown
    return " ".join(parts)


def _transform_attr(transform):
    """Generate SVG transform attribute value from a graphics transform."""
    return (
        f"matrix({_fmt(transform.r11)} {_fmt(transform.r12)} "
        f"{_fmt(transform.r21)} {_fmt(transform.r22)} "
        f"{_fmt(transform.tx)} {_fmt(-transform.ty)})"
    )


def _render_ops(ops, transform=None, link_resolver=None):
    """Render a list of graphics operations to SVG elements.

    Returns (svg_elements_string, bounding_box).
    link_resolver: optional callable(text) -> href_string_or_None
    """
    if transform is None:
        transform = OpGraphicsTransform(r11=1, r12=0, r21=0, r22=1, tx=0, ty=0)

    bb = BoundingBox()
    elements = []

    def tx(x):
        return x + transform.tx

    def ty(y):
        return y - transform.ty

    for op in ops:
        if isinstance(op, OpGraphicsTransform):
            transform = op
            continue

        if isinstance(op, OpScanConversionMode):
            sub_svg, sub_bb = _render_ops(op.output_forms, transform, link_resolver)
            elements.append(sub_svg)
            bb.extend_box(sub_bb)
            continue

        if isinstance(op, OpLine):
            x1 = tx(op.start_x)
            y1 = ty(-op.start_y)
            x2 = tx(op.end_x)
            y2 = ty(-op.end_y)
            bb.extend_point(x1, y1)
            bb.extend_point(x2, y2)
            elements.append(
                f'<line x1="{_fmt(x1)}" y1="{_fmt(y1)}" '
                f'x2="{_fmt(x2)}" y2="{_fmt(y2)}" '
                f'stroke="#000000" fill="none"/>'
            )

        elif isinstance(op, OpRectangle):
            filled = _plist_get(op.options, ':filled', True)
            thickness = _plist_get(op.options, ':thickness', 1)
            gray_level = _plist_get(op.options, ':gray-level')
            x = tx(min(op.left, op.right))
            y = ty(-max(op.top, op.bottom))
            w = abs(op.right - op.left)
            h = abs(op.bottom - op.top)
            bb.extend_point(x, y)
            bb.extend_point(x + w, y + h)
            if filled:
                fill = _gray_to_rgb(gray_level) if gray_level is not None else "#000000"
                elements.append(
                    f'<rect x="{_fmt(x)}" y="{_fmt(y)}" '
                    f'width="{_fmt(w)}" height="{_fmt(h)}" fill="{fill}"/>'
                )
            else:
                elements.append(
                    f'<rect x="{_fmt(x)}" y="{_fmt(y)}" '
                    f'width="{_fmt(w)}" height="{_fmt(h)}" '
                    f'stroke="#000000" stroke-width="{thickness}" fill="none"/>'
                )

        elif isinstance(op, OpEllipse):
            filled = _plist_get(op.options, ':filled', True)
            thickness = _plist_get(op.options, ':thickness', 1)
            gray_level = _plist_get(op.options, ':gray-level')
            cx = _fmt(tx(op.center_x))
            cy = _fmt(ty(op.center_y))
            rx = _fmt(op.radius_x)
            ry = _fmt(op.radius_y)
            if filled:
                fill = _gray_to_rgb(gray_level) if gray_level is not None else "#000000"
                elements.append(
                    f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}"/>'
                )
            else:
                elements.append(
                    f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
                    f'stroke="#000000" stroke-width="{thickness}" fill="none"/>'
                )

        elif isinstance(op, OpTriangle):
            filled = _plist_get(op.options, ':filled', True)
            thickness = _plist_get(op.options, ':thickness', 1)
            gray_level = _plist_get(op.options, ':gray-level')
            pts = _points_to_string([
                tx(op.x1), ty(-op.y1),
                tx(op.x2), ty(-op.y2),
                tx(op.x3), ty(-op.y3),
            ])
            if filled:
                fill = _gray_to_rgb(gray_level) if gray_level is not None else "#000000"
                elements.append(f'<polygon points="{pts}" fill="{fill}"/>')
            else:
                elements.append(
                    f'<polygon points="{pts}" stroke="#000000" '
                    f'stroke-width="{thickness}" fill="none"/>'
                )

        elif isinstance(op, OpPolygon):
            pts = _points_to_string(op.points)
            elements.append(f'<polygon points="{pts}" stroke="#000000"/>')

        elif isinstance(op, OpLines):
            thickness = _plist_get(op.options, ':thickness', 1)
            pts = _points_to_string(op.points, invert_y=True)
            t_attr = _transform_attr(transform)
            elements.append(
                f'<polyline points="{pts}" stroke="#000000" fill="none" '
                f'stroke-width="{thickness}" transform="{t_attr}"/>'
            )

        elif isinstance(op, (OpString, OpStringImage)):
            x = tx(op.x)
            y = ty(-op.y)
            bb.extend_point(x, y)
            bb.extend_point(x + len(op.string) * 10, y - 16)
            escaped = xml_escape(op.string)
            href = link_resolver(op.string) if link_resolver else None
            if href:
                elements.append(
                    f'<a href="{href}">'
                    f'<text x="{_fmt(x)}" y="{_fmt(y)}" fill="#1a5fa0">{escaped}</text>'
                    f'</a>'
                )
            else:
                elements.append(
                    f'<text x="{_fmt(x)}" y="{_fmt(y)}">{escaped}</text>'
                )

        elif isinstance(op, OpPath):
            filled = _plist_get(op.options, ':filled', True)
            thickness = _plist_get(op.options, ':thickness', 1)
            d = _path_to_svg(op.path_function)
            t_attr = _transform_attr(transform)
            fill_attr = '"#000000"' if filled else '"none"'
            stroke_attr = '' if filled else f' stroke="#000000" stroke-width="{thickness}"'
            elements.append(
                f'<path d="{d}" fill={fill_attr}{stroke_attr} transform="{t_attr}"/>'
            )

        elif isinstance(op, OpBezierCurve):
            thickness = _plist_get(op.options, ':thickness', 1)
            d = _points_to_cubic([
                op.start_x, op.start_y,
                op.control_1_x, op.control_1_y,
                op.control_2_x, op.control_2_y,
                op.end_x, op.end_y,
            ], invert_y=True)
            t_attr = _transform_attr(transform)
            elements.append(
                f'<path d="{d}" stroke="#000000" fill="none" '
                f'stroke-width="{thickness}" transform="{t_attr}"/>'
            )

        elif isinstance(op, OpCubicSpline):
            thickness = _plist_get(op.options, ':thickness', 1)
            d = _points_to_cubic(op.points, invert_y=True)
            t_attr = _transform_attr(transform)
            elements.append(
                f'<path d="{d}" stroke="#000000" fill="none" '
                f'stroke-width="{thickness}" transform="{t_attr}"/>'
            )

        elif isinstance(op, OpImage):
            x = tx(op.left)
            y = ty(op.top)
            img = op.image
            if isinstance(img, OpRasterImage):
                image_right = _plist_get(op.options, ':image-right')
                image_bottom = _plist_get(op.options, ':image-bottom')
                w = image_right if image_right else img.width
                h = image_bottom if image_bottom else img.height
                bb.extend_point(x, y)
                bb.extend_point(x + w, y + h)
                data_uri = raster_to_png_data_uri(img)
                elements.append(
                    f'<image x="{_fmt(x)}" y="{_fmt(y)}" '
                    f'width="{_fmt(w)}px" height="{_fmt(h)}px" '
                    f'href="{data_uri}"/>'
                )

        elif isinstance(op, OpPoint):
            x = tx(op.x)
            y = ty(op.y)
            bb.extend_point(x, y)
            elements.append(f'<circle cx="{_fmt(x)}" cy="{_fmt(y)}" r="1"/>')

    return "\n".join(elements), bb


def render_picture_to_svg(ops, link_resolver=None) -> str:
    """Render a list of decoded graphics operations to a complete SVG string."""
    transform = OpGraphicsTransform(r11=1, r12=0, r21=0, r22=1, tx=0, ty=0)
    content, bb = _render_ops(ops, transform, link_resolver)
    x = _fmt(bb.x1)
    y = _fmt(bb.y1)
    w = _fmt(bb.x2 - bb.x1)
    h = _fmt(bb.y2 - bb.y1)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="{x} {y} {w} {h}">\n'
        f'<g>\n{content}\n</g>\n</svg>'
    )
