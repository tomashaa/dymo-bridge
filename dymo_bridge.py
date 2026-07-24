#!/usr/bin/env python3
"""
dymo-bridge — a Linux-compatible clone of the DYMO Connect Web Service.

Reimplements just the three endpoints the SkyKeeper MRO app calls against
DYMO Connect on https://127.0.0.1:41951:

    GET  /DYMO/DLS/Printing/StatusConnected  -> "true"
    GET  /DYMO/DLS/Printing/GetPrinters      -> <Printers> XML built from CUPS
    POST /DYMO/DLS/Printing/PrintLabel        -> renders labelXml and prints via CUPS

It renders both DYMO XML dialects the app emits:
  * DYMO Label Framework v8  (<DieCutLabel>/<ContinuousLabel>, twips) — TextObject,
    ImageObject (embedded base64 PNG), BarcodeObject (QRCode).
  * DYMO Connect v3          (<DesktopLabel>/<DYMOLabel>, mm)  — text (test label).

Rendered to a 300-DPI raster, then sent to the matching CUPS queue with fit-to-page.

No sudo, no venv: runs as a `systemd --user` service using the system python3 with
python3-pil, python3-qrcode and python3-cups.
"""

import base64
import html
import io
import os
import re
import ssl
import subprocess
import sys
import tempfile
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw, ImageFont
import qrcode

try:
    import cups
except ImportError:
    cups = None

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

HOST = "127.0.0.1"
PORT = 41951
DPI = 300
TWIPS_PER_INCH = 1440.0
MM_PER_INCH = 25.4

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_FILE = os.path.join(BASE_DIR, "cert.pem")
KEY_FILE = os.path.join(BASE_DIR, "key.pem")
LOG_FILE = os.path.join(BASE_DIR, "dymo-bridge.log")

# Nominal die-cut label sizes, landscape (long_side_in, short_side_in).
# Used to size the canvas; printing uses fit-to-page so small mismatches are fine.
PAPER_SIZES_IN = {
    "30252 Address": (3.5, 1.125),
    "30321 Large Address": (3.5, 1.4),
    "30323 Shipping": (4.0, 2.125),
    "30256 Shipping": (4.0, 2.3125),
    "30270 Continuous": (6.0, 4.0),   # app uses this as a 4x6" hack for the 4XL
}

# CUPS PageSize names (points) for LabelWriter PPDs.
# Wrong media (e.g. default w167h288 = 4" feed) makes one job span TWO physical labels.
PAPER_TO_CUPS_MEDIA = {
    "30252 Address": "w79h252",          # ~28 x 89 mm
    "30321 Large Address": "w102h252",   # 36 x 89 mm (S0722400 / Large Address)
    "30323 Shipping": "w154h286",        # ~54 x 101 mm
    "30256 Shipping": "w167h252",        # ~59 x 89 mm
    "30270 Continuous": "w296h452",      # ~4 x 6 in (4XL)
}

# Arial/Helvetica -> Liberation Sans (metric compatible); Courier -> Liberation Mono.
FONT_DIRS = [
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/truetype/dejavu",
]
FONT_MAP = {
    "sans": {
        (False, False): "LiberationSans-Regular.ttf",
        (True, False): "LiberationSans-Bold.ttf",
        (False, True): "LiberationSans-Italic.ttf",
        (True, True): "LiberationSans-BoldItalic.ttf",
    },
    "mono": {
        (False, False): "LiberationMono-Regular.ttf",
        (True, False): "LiberationMono-Bold.ttf",
        (False, True): "LiberationMono-Italic.ttf",
        (True, True): "LiberationMono-BoldItalic.ttf",
    },
}
FONT_FALLBACK = "DejaVuSans.ttf"

_font_cache = {}


def log(msg):
    line = f"{datetime.now().isoformat(timespec='seconds')}  {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Units
# --------------------------------------------------------------------------- #

def twips_to_px(twips):
    return int(round(float(twips) / TWIPS_PER_INCH * DPI))


def mm_to_px(mm):
    return int(round(float(mm) / MM_PER_INCH * DPI))


def pt_to_px(pt):
    return max(1, int(round(float(pt) / 72.0 * DPI)))


# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #

def _find_font_file(filename):
    for d in FONT_DIRS:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return None


def resolve_font(family, size_pt, bold=False, italic=False):
    fam = (family or "").lower()
    kind = "mono" if ("courier" in fam or "mono" in fam or "consol" in fam) else "sans"
    filename = FONT_MAP[kind].get((bold, italic)) or FONT_MAP[kind][(False, False)]
    path = _find_font_file(filename) or _find_font_file(FONT_FALLBACK)
    px = pt_to_px(size_pt)
    key = (path, px)
    if key not in _font_cache:
        try:
            _font_cache[key] = ImageFont.truetype(path, px)
        except Exception:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def text_size(draw, text, font):
    """Width/height of a possibly multi-line string."""
    lines = text.split("\n") or [""]
    w = 0
    h = 0
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln if ln else " ", font=font)
        w = max(w, bbox[2] - bbox[0])
        h += (bbox[3] - bbox[1]) + int(font.size * 0.25)
    return w, h


# --------------------------------------------------------------------------- #
# XML helpers
# --------------------------------------------------------------------------- #

def _t(el, tag, default=""):
    if el is None:
        return default
    child = el.find(tag)
    return child.text if (child is not None and child.text is not None) else default


def _b(val):
    return str(val).strip().lower() in ("true", "1", "yes")


# --------------------------------------------------------------------------- #
# Rendering — object drawing
# --------------------------------------------------------------------------- #

def draw_text_object(img, draw, obj, box):
    """box = (x, y, w, h) in pixels. obj = <TextObject> element (dialect A)."""
    x, y, w, h = box

    # Collect styled runs -> combined string + a representative font spec.
    styled = obj.find("StyledText")
    runs = []
    if styled is not None:
        for el in styled.findall("Element"):
            s = _t(el, "String", "")
            attrs = el.find("Attributes")
            font_el = attrs.find("Font") if attrs is not None else None
            fam = font_el.get("Family", "Arial") if font_el is not None else "Arial"
            size = float(font_el.get("Size", "10")) if font_el is not None else 10.0
            bold = _b(font_el.get("Bold", "False")) if font_el is not None else False
            italic = _b(font_el.get("Italic", "False")) if font_el is not None else False
            fore = attrs.find("ForeColor") if attrs is not None else None
            color = color_from(fore) if fore is not None else (0, 0, 0)
            runs.append({"text": s, "family": fam, "size": size,
                         "bold": bold, "italic": italic, "color": color})
    if not runs:
        return

    text = "".join(r["text"] for r in runs)
    spec = runs[0]
    halign = _t(obj, "HorizontalAlignment", "Left")
    valign = _t(obj, "VerticalAlignment", "Top")
    fit = _t(obj, "TextFitMode", "None")

    size = spec["size"]
    font = resolve_font(spec["family"], size, spec["bold"], spec["italic"])
    if fit in ("ShrinkToFit", "AlwaysFit"):
        # shrink font until the whole block fits the box
        while size > 3:
            font = resolve_font(spec["family"], size, spec["bold"], spec["italic"])
            tw, th = text_size(draw, text, font)
            if tw <= w and th <= h:
                break
            size -= 0.5

    lines = text.split("\n")
    line_h = int(font.size * 1.25) or 1
    total_h = line_h * len(lines)
    cy = y
    if valign == "Middle":
        cy = y + max(0, (h - total_h) // 2)
    elif valign == "Bottom":
        cy = y + max(0, h - total_h)

    for ln in lines:
        bbox = draw.textbbox((0, 0), ln if ln else " ", font=font)
        lw = bbox[2] - bbox[0]
        cx = x
        if halign == "Center":
            cx = x + max(0, (w - lw) // 2)
        elif halign == "Right":
            cx = x + max(0, w - lw)
        draw.text((cx, cy), ln, fill=spec["color"], font=font)
        cy += line_h


def draw_image_object(img, obj, box):
    x, y, w, h = box
    b64 = _t(obj, "Image", "").strip()
    if not b64:
        return
    try:
        raw = base64.b64decode(b64)
        src = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception as e:
        log(f"  image decode failed: {e}")
        return
    scale = _t(obj, "ScaleMode", "Uniform")
    if scale.lower().startswith("uniform"):
        ratio = min(w / src.width, h / src.height)
        nw, nh = max(1, int(src.width * ratio)), max(1, int(src.height * ratio))
    else:
        nw, nh = w, h
    src = src.resize((nw, nh), Image.LANCZOS)

    halign = _t(obj, "HorizontalAlignment", "Left")
    valign = _t(obj, "VerticalAlignment", "Top")
    px = x + (0 if halign == "Left" else (w - nw) // 2 if halign == "Center" else w - nw)
    py = y + (0 if valign == "Top" else (h - nh) // 2 if valign == "Middle" else h - nh)
    img.paste(src, (px, py), src)


def draw_barcode_object(img, obj, box):
    x, y, w, h = box
    btype = _t(obj, "Type", "QRCode")
    data = _t(obj, "Text", "")
    if btype != "QRCode":
        log(f"  unsupported barcode type '{btype}' — skipped")
        return
    ec = _t(obj, "ECLevel", "0")
    ec_map = {"0": qrcode.constants.ERROR_CORRECT_L,
              "1": qrcode.constants.ERROR_CORRECT_M,
              "2": qrcode.constants.ERROR_CORRECT_Q,
              "3": qrcode.constants.ERROR_CORRECT_H}
    qr = qrcode.QRCode(error_correction=ec_map.get(ec, qrcode.constants.ERROR_CORRECT_L),
                       border=1, box_size=10)
    qr.add_data(data)
    qr.make(fit=True)
    code = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    side = min(w, h)
    code = code.resize((side, side), Image.NEAREST)

    halign = _t(obj, "HorizontalAlignment", "Center")
    px = x + (0 if halign == "Left" else (w - side) // 2 if halign == "Center" else w - side)
    py = y + (h - side) // 2
    img.paste(code, (px, py))


def color_from(el):
    try:
        return (int(el.get("Red", 0)), int(el.get("Green", 0)), int(el.get("Blue", 0)))
    except Exception:
        return (0, 0, 0)


# --------------------------------------------------------------------------- #
# Rendering — label dispatch
# --------------------------------------------------------------------------- #

def render_dialect_a(root):
    """DieCutLabel / ContinuousLabel, units = twips."""
    is_continuous = root.tag == "ContinuousLabel"
    paper = _t(root, "PaperName", "")
    orient = _t(root, "PaperOrientation", "Landscape")

    objs = root.findall(".//ObjectInfo")

    # canvas size in twips
    size_in = PAPER_SIZES_IN.get(paper)
    if size_in:
        long_in, short_in = size_in
        if orient == "Portrait":
            w_tw, h_tw = short_in * TWIPS_PER_INCH, long_in * TWIPS_PER_INCH
        else:
            w_tw, h_tw = long_in * TWIPS_PER_INCH, short_in * TWIPS_PER_INCH
    else:
        # fall back to the union of all object bounds
        max_x = max_y = 0
        for oi in objs:
            b = oi.find("Bounds")
            if b is not None:
                max_x = max(max_x, float(b.get("X", 0)) + float(b.get("Width", 0)))
                max_y = max(max_y, float(b.get("Y", 0)) + float(b.get("Height", 0)))
        w_tw, h_tw = max_x + 100, max_y + 100

    if is_continuous:
        length = _t(root, "LabelLength", "")
        if length:
            if orient == "Portrait":
                h_tw = float(length)
            else:
                w_tw = float(length)

    W, H = max(1, twips_to_px(w_tw)), max(1, twips_to_px(h_tw))
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    for oi in objs:
        b = oi.find("Bounds")
        if b is None:
            continue
        box = (twips_to_px(b.get("X", 0)), twips_to_px(b.get("Y", 0)),
               max(1, twips_to_px(b.get("Width", 0))), max(1, twips_to_px(b.get("Height", 0))))
        try:
            if oi.find("TextObject") is not None:
                draw_text_object(img, draw, oi.find("TextObject"), box)
            elif oi.find("ImageObject") is not None:
                draw_image_object(img, oi.find("ImageObject"), box)
            elif oi.find("BarcodeObject") is not None:
                draw_barcode_object(img, oi.find("BarcodeObject"), box)
        except Exception as e:
            log(f"  object render error: {e}")
    return img


def render_dialect_b(root):
    """DesktopLabel / DYMOLabel v3, units = mm. Text objects only (test label)."""
    dymo = root.find("DYMOLabel")
    rect = dymo.find("DYMORect") if dymo is not None else None
    size = rect.find("Size") if rect is not None else None
    w_mm = float(_t(size, "Width", "89"))
    h_mm = float(_t(size, "Height", "36"))
    W, H = max(1, mm_to_px(w_mm)), max(1, mm_to_px(h_mm))
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    objs = root.findall(".//LabelObjects/*")
    for o in objs:
        layout = o.find("ObjectLayout")
        pt = layout.find("DYMOPoint") if layout is not None else None
        sz = layout.find("Size") if layout is not None else None
        if pt is None or sz is None:
            continue
        box = (mm_to_px(_t(pt, "X", "0")), mm_to_px(_t(pt, "Y", "0")),
               max(1, mm_to_px(_t(sz, "Width", "10"))), max(1, mm_to_px(_t(sz, "Height", "10"))))
        if o.tag == "TextObject":
            ft = o.find(".//FormattedText")
            spans = ft.findall(".//TextSpan") if ft is not None else []
            text = "".join(_t(s, "Text", "") for s in spans)
            fi = spans[0].find("FontInfo") if spans else None
            fam = _t(fi, "FontName", "Arial")
            size_pt = float(_t(fi, "FontSize", "10"))
            bold = _b(_t(fi, "IsBold", "False"))
            italic = _b(_t(fi, "IsItalic", "False"))
            font = resolve_font(fam, size_pt, bold, italic)
            draw.multiline_text((box[0], box[1]), text, fill=(0, 0, 0), font=font)
    return img


def render_label(label_xml):
    label_xml = label_xml.strip()
    if label_xml.startswith("﻿"):
        label_xml = label_xml.lstrip("﻿")
    root = ET.fromstring(label_xml)
    if root.tag in ("DieCutLabel", "ContinuousLabel"):
        return render_dialect_a(root)
    if root.tag == "DesktopLabel":
        return render_dialect_b(root)
    raise ValueError(f"Unknown label root <{root.tag}>")


# --------------------------------------------------------------------------- #
# CUPS
# --------------------------------------------------------------------------- #

def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def list_dymo_printers():
    """Returns list of dicts: {queue, name, model, twinturbo}."""
    result = []
    if cups is None:
        return result
    try:
        conn = cups.Connection()
        printers = conn.getPrinters()
    except Exception as e:
        log(f"CUPS connection failed: {e}")
        return result
    for name, attrs in printers.items():
        uri = (attrs.get("device-uri") or "").lower()
        model = attrs.get("printer-make-and-model", "") or ""
        if "dymo" in uri or "dymo" in model.lower() or "labelwriter" in model.lower():
            result.append({
                "queue": name,
                "name": name,
                "model": model or name,
                "twinturbo": ("twin" in model.lower() or "duo" in model.lower()
                              or "duo" in name.lower()),
            })
    return result


def match_queue(printer_name):
    """Fuzzy-match the DYMO printerName the app sends to a real CUPS queue."""
    printers = list_dymo_printers()
    if not printers:
        return None
    want = _norm(printer_name)
    # exact queue name
    for p in printers:
        if _norm(p["queue"]) == want:
            return p["queue"]
    # Prefer specific model tokens before generic fallbacks (avoid DUO→4XL).
    for token in ("4xl", "450duo", "twinturbo", "duo", "450", "550", "5xl"):
        if token in want:
            for p in printers:
                blob = _norm(p["queue"]) + _norm(p["model"])
                if token in blob:
                    return p["queue"]
    # substring either way
    for p in printers:
        qn = _norm(p["queue"])
        if want and (want in qn or qn in want):
            return p["queue"]
    # Only auto-pick when there is exactly one DYMO queue — never silently
    # send a DUO/4XL job to the wrong printer.
    if len(printers) == 1:
        return printers[0]["queue"]
    log(f"  ambiguous printerName='{printer_name}' among {[p['queue'] for p in printers]}")
    return None


def parse_paper_name(label_xml):
    m = re.search(r"<PaperName>\s*([^<]+?)\s*</PaperName>", label_xml or "")
    return m.group(1).strip() if m else ""


def print_image(queue, img, copies=1, paper_name=""):
    # LabelWriter feeds along the long edge; raster width = across print head (short side).
    # SkyKeeper DieCutLabel landscape canvases are long×short — rotate before CUPS.
    if img.width > img.height:
        img = img.transpose(Image.ROTATE_270)

    fd, path = tempfile.mkstemp(suffix=".png", prefix="dymo-", dir=BASE_DIR)
    os.close(fd)
    img.convert("L").save(path, "PNG", dpi=(DPI, DPI))

    media = PAPER_TO_CUPS_MEDIA.get(paper_name) or PAPER_TO_CUPS_MEDIA.get("30321 Large Address")
    options = {
        "fit-to-page": "true",
        "copies": str(max(1, copies)),
        "media": media,
    }
    title = "SkyKeeper Label"
    try:
        if cups is not None:
            conn = cups.Connection()
            job = conn.printFile(queue, path, title, options)
            log(f"  submitted CUPS job {job} to '{queue}' ({copies} copy/ies) media={media} paper='{paper_name}'")
            return True
        else:
            cmd = ["lp", "-d", queue, "-n", str(copies),
                   "-o", "fit-to-page", "-o", f"media={media}", path]
            subprocess.run(cmd, check=True)
            return True
    except Exception as e:
        log(f"  print failed: {e}")
        return False
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def parse_copies(print_params_xml):
    if not print_params_xml:
        return 1
    m = re.search(r"<Copies>\s*(\d+)\s*</Copies>", print_params_xml)
    return int(m.group(1)) if m else 1


def build_printers_xml():
    printers = list_dymo_printers()
    parts = ['<?xml version="1.0" encoding="utf-8"?>', "<Printers>"]
    for p in printers:
        tag = "TapePrinter" if False else "LabelWriterPrinter"
        parts.append(f"  <{tag}>")
        parts.append(f"    <Name>{html.escape(p['name'])}</Name>")
        parts.append(f"    <ModelName>{html.escape(p['model'])}</ModelName>")
        parts.append("    <IsConnected>True</IsConnected>")
        parts.append("    <IsLocal>True</IsLocal>")
        parts.append(f"    <IsTwinTurbo>{'True' if p['twinturbo'] else 'False'}</IsTwinTurbo>")
        parts.append(f"  </{tag}>")
    parts.append("</Printers>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# TLS
# --------------------------------------------------------------------------- #

def ensure_cert():
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        return
    log("generating self-signed certificate for 127.0.0.1 / localhost ...")
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", KEY_FILE, "-out", CERT_FILE, "-days", "3650",
        "-subj", "/CN=127.0.0.1",
        "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost,IP:::1",
    ], check=True)
    os.chmod(KEY_FILE, 0o600)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #

STATUS_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>dymo-bridge</title></head><body style="font-family:sans-serif;max-width:40em;margin:3em auto">
<h2>✅ dymo-bridge is running</h2>
<p>Linux clone of the DYMO Connect Web Service for SkyKeeper.</p>
<p>If you reached this page, the self-signed certificate is now trusted for this browser —
label printing from the app should work.</p>
<p>Printers detected: <b>{printers}</b></p>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "dymo-bridge/1.0"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, body, code=200, ctype="text/plain; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # quiet; we do our own logging

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")
        if path.endswith("/StatusConnected") or path.endswith("/Check"):
            self._send("true")
        elif path.endswith("/GetPrinters"):
            self._send(build_printers_xml(), ctype="text/xml; charset=utf-8")
        elif path in ("", "/"):
            names = ", ".join(p["name"] for p in list_dymo_printers()) or "none"
            self._send(STATUS_PAGE.format(printers=html.escape(names)),
                       ctype="text/html; charset=utf-8")
        else:
            self._send("true")  # be permissive for other status probes

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        # SkyKeeper tries PrintLabel2 first, then PrintLabel — handle both.
        if not (path.endswith("/PrintLabel") or path.endswith("/PrintLabel2")):
            self._send("true")
            return
        try:
            form = parse_qs(raw, keep_blank_values=True)
            printer_name = (form.get("printerName", [""])[0])
            label_xml = form.get("labelXml", [""])[0]
            params_xml = form.get("printParamsXml", [""])[0]
            copies = parse_copies(params_xml)
            paper_name = parse_paper_name(label_xml)
            log(f"PrintLabel: printer='{printer_name}' copies={copies} paper='{paper_name}' xml={len(label_xml)}B")

            queue = match_queue(printer_name)
            if not queue:
                log("  no DYMO CUPS queue found")
                self._send("no printer", code=500)
                return

            img = render_label(label_xml)
            ok = print_image(queue, img, copies, paper_name=paper_name)
            self._send("1" if ok else "0", code=200 if ok else 500)
        except Exception as e:
            log("  PrintLabel error:\n" + traceback.format_exc())
            self._send(f"error: {e}", code=500)


def main():
    ensure_cert()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT_FILE, KEY_FILE)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    printers = ", ".join(p["queue"] for p in list_dymo_printers()) or "none yet"
    log(f"dymo-bridge listening on https://{HOST}:{PORT}  (CUPS printers: {printers})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("shutting down")


if __name__ == "__main__":
    main()
