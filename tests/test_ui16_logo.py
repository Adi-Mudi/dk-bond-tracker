import json
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "src" / "static" / "img" / "logo"
ANDROID_RES = ROOT / "android" / "app" / "src" / "main" / "res"
BASE_HTML = (ROOT / "src" / "templates" / "base.html").read_text(encoding="utf-8")
ABOUT_HTML = (ROOT / "src" / "templates" / "about.html").read_text(encoding="utf-8")
MANIFEST = ROOT / "src" / "static" / "site.webmanifest"

DENSITY_SIZES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}


def png_header(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path
    width, height, depth, colour = struct.unpack(">IIBB", data[16:26])
    return width, height, depth, colour


def png_rgba(path):
    data = path.read_bytes()
    width, height, depth, colour = struct.unpack(">IIBB", data[16:26])
    assert (depth, colour) == (8, 6), (path.name, depth, colour)
    pos = 8
    idat = b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        if kind == b"IDAT":
            idat += data[pos + 8 : pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 4
    out = bytearray(height * stride)
    prev = bytearray(stride)
    offset = 0
    for y in range(height):
        kind = raw[offset]
        offset += 1
        line = bytearray(raw[offset : offset + stride])
        offset += stride
        if kind == 1:
            for i in range(4, stride):
                line[i] = (line[i] + line[i - 4]) & 0xFF
        elif kind == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif kind == 3:
            for i in range(stride):
                left = line[i - 4] if i >= 4 else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif kind == 4:
            for i in range(stride):
                a = line[i - 4] if i >= 4 else 0
                b = prev[i]
                c = prev[i - 4] if i >= 4 else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                if pa <= pb and pa <= pc:
                    pred = a
                elif pb <= pc:
                    pred = b
                else:
                    pred = c
                line[i] = (line[i] + pred) & 0xFF
        out[y * stride : (y + 1) * stride] = line
        prev = line
    return width, height, bytes(out)


def ink_bbox(path, threshold=30):
    width, height, pixels = png_rgba(path)
    min_x, min_y, max_x, max_y = width, height, -1, -1
    radius = 0.0
    for y in range(height):
        row = y * width * 4
        for x in range(width):
            i = row + x * 4
            if pixels[i + 3] <= 8:
                continue
            r, g, b = pixels[i], pixels[i + 1], pixels[i + 2]
            if (max(r, g, b) - min(r, g, b)) > threshold:
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
                dx = (x + 0.5) / width - 0.5
                dy = (y + 0.5) / height - 0.5
                distance = (dx * dx + dy * dy) ** 0.5
                if distance > radius:
                    radius = distance
    assert max_x >= 0, path
    return min_x / width, min_y / height, (max_x + 1) / width, (max_y + 1) / height, radius


def test_ui16_favicon_png_set_exists_at_required_sizes():
    for name in (
        "favicon-32.png",
        "icon-192.png",
        "icon-512-maskable.png",
        "apple-touch-icon-180.png",
        "logo-512.png",
        "logo-1024.png",
        "logo-monochrome-512.png",
    ):
        path = LOGO / name
        assert path.is_file(), name
    assert png_header(LOGO / "favicon-32.png")[:2] == (32, 32)
    assert png_header(LOGO / "icon-192.png")[:2] == (192, 192)
    assert png_header(LOGO / "icon-512-maskable.png")[:2] == (512, 512)
    assert png_header(LOGO / "apple-touch-icon-180.png")[:2] == (180, 180)
    assert png_header(LOGO / "logo-512.png")[:2] == (512, 512)
    assert png_header(LOGO / "logo-1024.png")[:2] == (1024, 1024)


def test_ui16_svg_masters_exist():
    for name in ("logo-master.svg", "logo-mark.svg", "logo-monochrome.svg", "favicon.svg"):
        path = LOGO / name
        assert path.is_file(), name
        assert "viewBox" in path.read_text(encoding="utf-8")


def test_ui16_apple_touch_icon_is_opaque():
    width, height, depth, colour = png_header(LOGO / "apple-touch-icon-180.png")
    assert (width, height) == (180, 180)
    assert colour == 2, "apple-touch-icon must be opaque RGB (no alpha channel)"


def test_ui16_maskable_mark_sits_inside_the_safe_zone():
    x0, y0, x1, y1, radius = ink_bbox(LOGO / "icon-512-maskable.png")
    assert x0 >= 0.10
    assert y0 >= 0.10
    assert x1 <= 0.90
    assert y1 <= 0.90
    assert radius <= 0.40 + 0.005


def test_ui16_full_master_mark_fills_the_canvas():
    x0, y0, x1, y1, _radius = ink_bbox(LOGO / "logo-512.png")
    assert (x1 - x0) > 0.60
    assert (y1 - y0) > 0.60


def test_ui16_base_html_wires_the_icon_set_with_cache_bust():
    brand = (Path("src/templates") / "_brand.html").read_text(encoding="utf-8")
    assert 'href="/static/img/logo/favicon.svg?v=2"' in brand
    assert 'href="/static/img/logo/favicon-32.png?v=2"' in brand
    assert 'apple-touch-icon' in brand
    assert 'rel="manifest"' in brand
    assert "{{ brand_head() }}" in BASE_HTML


def test_ui16_header_lockup_uses_the_simplified_mark():
    brand = (Path("src/templates") / "_brand.html").read_text(encoding="utf-8")
    assert 'src="/static/img/logo/logo-mark.svg?v=2"' in brand
    assert "{{ brand_mark(24) }}" in BASE_HTML
    assert "brand-mark" in BASE_HTML
    assert "logo-maskable" not in BASE_HTML
    assert "icon-512-maskable" not in BASE_HTML


def test_ui16_about_page_shows_the_logo_avatar():
    brand = (Path("src/templates") / "_brand.html").read_text(encoding="utf-8")
    assert 'src="/static/img/logo/logo-512.png?v=2"' in brand
    assert "brand_avatar" in ABOUT_HTML
    assert 'id="about-avatar"' in brand


def test_ui16_manifest_marks_the_maskable_purpose():
    assert MANIFEST.is_file()
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    purposes = [icon.get("purpose") for icon in data["icons"]]
    assert "maskable" in purposes
    maskable = [icon for icon in data["icons"] if icon.get("purpose") == "maskable"]
    assert maskable[0]["src"].endswith("icon-512-maskable.png")
    assert maskable[0]["sizes"] == "512x512"


def test_ui16_android_adaptive_icon_layers_exist():
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        path = ANDROID_RES / "mipmap-anydpi-v26" / name
        assert path.is_file(), name
        text = path.read_text(encoding="utf-8")
        assert "<adaptive-icon" in text
        assert "@drawable/ic_launcher_background" in text
        assert "@drawable/ic_launcher_foreground" in text
        assert "<monochrome" in text
        assert "@drawable/ic_launcher_monochrome" in text


def test_ui16_android_density_mipmaps_exist():
    for density, size in DENSITY_SIZES.items():
        for name in ("ic_launcher.png", "ic_launcher_round.png"):
            path = ANDROID_RES / ("mipmap-%s" % density) / name
            assert path.is_file(), (density, name)
            assert png_header(path)[:2] == (size, size)


def test_ui16_android_layers_and_manifest_reference():
    for name in (
        "ic_launcher_background.png",
        "ic_launcher_foreground.png",
        "ic_launcher_monochrome.png",
    ):
        path = ANDROID_RES / "drawable" / name
        assert path.is_file(), name
        assert png_header(path)[:2] == (432, 432)
    manifest = (ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(
        encoding="utf-8"
    )
    assert 'android:icon="@mipmap/ic_launcher"' in manifest
    assert 'android:roundIcon="@mipmap/ic_launcher_round"' in manifest


def test_ui16_android_foreground_stays_inside_the_66dp_safe_zone():
    x0, y0, x1, y1, radius = ink_bbox(
        ANDROID_RES / "drawable" / "ic_launcher_foreground.png"
    )
    assert x0 >= 0.194 - 0.01
    assert y0 >= 0.194 - 0.01
    assert x1 <= 0.806 + 0.01
    assert y1 <= 0.806 + 0.01
    assert radius <= (33.0 / 108.0) + 0.005
