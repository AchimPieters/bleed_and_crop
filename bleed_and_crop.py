
#!/usr/bin/env python3
"""
Maak een print-PDF met:
1. witte randen automatisch weggesneden
2. bleed opgebouwd door alle zijden/hoeken te spiegelen
3. snijtekens buiten het artwork

Standaard outputnaam:
    <input_stem>_Print.pdf

Voorbeeld:
    python make_print_pdf.py input.pdf
    python make_print_pdf.py input.pdf -o output.pdf --bleed-mm 3 --mark-margin-mm 8
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable, Tuple

import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageDraw


def mm_to_px(mm: float, dpi: int) -> int:
    return max(1, int(round(mm / 25.4 * dpi)))


def find_nonwhite_bbox(
    img: Image.Image,
    threshold: int = 245,
    pad_px: int = 0,
    edge_activity_threshold: float = 0.02,
) -> Tuple[int, int, int, int]:
    """
    Zoek de bounding box van alles wat niet (bijna) wit is.

    Extra stap:
    volledig of bijna lege buitenste rijen/kolommen (bv. 1-2 witte anti-aliased lijnen)
    worden eerst weggehaald. Dat voorkomt witte haarlijnen in het uiteindelijke bleed.
    Retourneert (left, top, right, bottom), waarbij right/bottom exclusief zijn.
    """
    rgb = np.asarray(img.convert("RGB"))
    nonwhite = np.any(rgb < threshold, axis=2)

    if not np.any(nonwhite):
        return 0, 0, img.width, img.height

    row_activity = nonwhite.mean(axis=1)
    col_activity = nonwhite.mean(axis=0)

    top = 0
    while top < img.height - 1 and row_activity[top] < edge_activity_threshold:
        top += 1

    bottom = img.height
    while bottom > top + 1 and row_activity[bottom - 1] < edge_activity_threshold:
        bottom -= 1

    left = 0
    while left < img.width - 1 and col_activity[left] < edge_activity_threshold:
        left += 1

    right = img.width
    while right > left + 1 and col_activity[right - 1] < edge_activity_threshold:
        right -= 1

    top = max(0, top - pad_px)
    bottom = min(img.height, bottom + pad_px)
    left = max(0, left - pad_px)
    right = min(img.width, right + pad_px)
    return left, top, right, bottom


def render_page(page: fitz.Page, dpi: int, clip: fitz.Rect | None = None) -> Image.Image:
    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
    mode = "RGB"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def add_mirrored_bleed(trim_img: Image.Image, bleed_px: int) -> Image.Image:
    """
    Spiegel alle randen én hoeken om bleed op te bouwen.
    """
    if bleed_px <= 0:
        return trim_img.copy()

    src = trim_img.convert("RGB")
    w, h = src.size
    out = Image.new("RGB", (w + 2 * bleed_px, h + 2 * bleed_px), "white")
    out.paste(src, (bleed_px, bleed_px))

    # Randen
    top = src.crop((0, 0, w, bleed_px)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    bottom = src.crop((0, h - bleed_px, w, h)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    left = src.crop((0, 0, bleed_px, h)).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    right = src.crop((w - bleed_px, 0, w, h)).transpose(Image.Transpose.FLIP_LEFT_RIGHT)

    out.paste(top, (bleed_px, 0))
    out.paste(bottom, (bleed_px, bleed_px + h))
    out.paste(left, (0, bleed_px))
    out.paste(right, (bleed_px + w, bleed_px))

    # Hoeken
    tl = src.crop((0, 0, bleed_px, bleed_px)).transpose(Image.Transpose.ROTATE_180)
    tr = src.crop((w - bleed_px, 0, w, bleed_px)).transpose(Image.Transpose.ROTATE_180)
    bl = src.crop((0, h - bleed_px, bleed_px, h)).transpose(Image.Transpose.ROTATE_180)
    br = src.crop((w - bleed_px, h - bleed_px, w, h)).transpose(Image.Transpose.ROTATE_180)

    out.paste(tl, (0, 0))
    out.paste(tr, (bleed_px + w, 0))
    out.paste(bl, (0, bleed_px + h))
    out.paste(br, (bleed_px + w, bleed_px + h))
    return out


def add_crop_marks(
    artwork: Image.Image,
    bleed_px: int,
    mark_margin_px: int,
    mark_len_px: int,
    stroke_px: int,
    color: tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """
    Plaatst artwork op een witte pagina met snijtekens buiten het bleedgebied.
    Snijtekens markeren de trimbox.
    """
    aw, ah = artwork.size
    canvas = Image.new("RGB", (aw + 2 * mark_margin_px, ah + 2 * mark_margin_px), "white")
    canvas.paste(artwork, (mark_margin_px, mark_margin_px))

    draw = ImageDraw.Draw(canvas)

    trim_left = mark_margin_px + bleed_px
    trim_top = mark_margin_px + bleed_px
    trim_right = trim_left + (aw - 2 * bleed_px)
    trim_bottom = trim_top + (ah - 2 * bleed_px)

    # horizontale markeringen links/rechts van boven- en onderrand
    for y in (trim_top, trim_bottom):
        draw.line(
            [(trim_left - mark_len_px, y), (trim_left - 1, y)],
            fill=color,
            width=stroke_px,
        )
        draw.line(
            [(trim_right + 1, y), (trim_right + mark_len_px, y)],
            fill=color,
            width=stroke_px,
        )

    # verticale markeringen boven/onder links- en rechterrand
    for x in (trim_left, trim_right):
        draw.line(
            [(x, trim_top - mark_len_px), (x, trim_top - 1)],
            fill=color,
            width=stroke_px,
        )
        draw.line(
            [(x, trim_bottom + 1), (x, trim_bottom + mark_len_px)],
            fill=color,
            width=stroke_px,
        )

    return canvas


def process_pdf(
    input_pdf: Path,
    output_pdf: Path,
    *,
    analysis_dpi: int = 72,
    output_dpi: int = 300,
    threshold: int = 245,
    bbox_pad_mm: float = 0.0,
    bleed_mm: float = 3.0,
    mark_margin_mm: float = 8.0,
    mark_len_mm: float = 5.0,
    stroke_mm: float = 0.2,
) -> None:
    analysis_pad_px = mm_to_px(bbox_pad_mm, analysis_dpi)
    bleed_px = mm_to_px(bleed_mm, output_dpi)
    mark_margin_px = mm_to_px(mark_margin_mm, output_dpi)
    mark_len_px = mm_to_px(mark_len_mm, output_dpi)
    stroke_px = max(1, mm_to_px(stroke_mm, output_dpi))

    doc = fitz.open(input_pdf)
    output_pages: list[Image.Image] = []

    for page in doc:
        # 1) Zoek eerst de trimbox door witte randen in een snelle lage resolutie render te detecteren.
        preview = render_page(page, analysis_dpi)
        left, top, right, bottom = find_nonwhite_bbox(preview, threshold=threshold, pad_px=analysis_pad_px)

        # Converteer afbeeldingsbbox -> PDF coördinaten
        pdf_rect = page.rect
        sx = pdf_rect.width / preview.width
        sy = pdf_rect.height / preview.height
        clip = fitz.Rect(left * sx, top * sy, right * sx, bottom * sy)

        # 2) Render alleen het gesneden gebied op uiteindelijke resolutie
        trim_img = render_page(page, output_dpi, clip=clip)

        # 2b) Een clip precies op de page edge kan door renderer-rounding
        # toch nog 1-3 witte haarlijnen opleveren. Daarom nogmaals op de
        # hoge resolutie trimmen voordat bleed wordt opgebouwd.
        t_left, t_top, t_right, t_bottom = find_nonwhite_bbox(
            trim_img,
            threshold=threshold,
            pad_px=0,
        )
        trim_img = trim_img.crop((t_left, t_top, t_right, t_bottom))

        # 3) Spiegel zijden + hoeken voor bleed
        with_bleed = add_mirrored_bleed(trim_img, bleed_px)

        # 4) Snijtekens toevoegen op witte marge buiten het artwork
        final_page = add_crop_marks(
            with_bleed,
            bleed_px=bleed_px,
            mark_margin_px=mark_margin_px,
            mark_len_px=mark_len_px,
            stroke_px=stroke_px,
        )
        output_pages.append(final_page)

    if not output_pages:
        raise RuntimeError("Geen pagina's gevonden in de input-PDF.")

    output_pages[0].save(
        output_pdf,
        save_all=True,
        append_images=output_pages[1:],
        resolution=output_dpi,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Maak een printklare PDF met mirrored bleed en snijtekens.")
    p.add_argument("input_pdf", type=Path, help="Input PDF")
    p.add_argument("-o", "--output", dest="output_pdf", type=Path, help="Output PDF. Standaard: <input>_Print.pdf")
    p.add_argument("--analysis-dpi", type=int, default=72, help="DPI voor randdetectie")
    p.add_argument("--output-dpi", type=int, default=300, help="DPI voor output")
    p.add_argument("--threshold", type=int, default=245, help="Wit-drempel (0-255) voor randdetectie")
    p.add_argument("--bbox-pad-mm", type=float, default=0.0, help="Extra marge rondom gevonden trimbox")
    p.add_argument("--bleed-mm", type=float, default=3.0, help="Bleed rondom trimformaat")
    p.add_argument("--mark-margin-mm", type=float, default=8.0, help="Witte marge buiten artwork voor snijtekens")
    p.add_argument("--mark-len-mm", type=float, default=5.0, help="Lengte van snijtekens")
    p.add_argument("--stroke-mm", type=float, default=0.2, help="Lijndikte van snijtekens")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_pdf = args.input_pdf
    output_pdf = args.output_pdf or input_pdf.with_name(f"{input_pdf.stem}_Print.pdf")

    process_pdf(
        input_pdf,
        output_pdf,
        analysis_dpi=args.analysis_dpi,
        output_dpi=args.output_dpi,
        threshold=args.threshold,
        bbox_pad_mm=args.bbox_pad_mm,
        bleed_mm=args.bleed_mm,
        mark_margin_mm=args.mark_margin_mm,
        mark_len_mm=args.mark_len_mm,
        stroke_mm=args.stroke_mm,
    )
    print(f"Gemaakt: {output_pdf}")


if __name__ == "__main__":
    main()
