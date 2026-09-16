import argparse
import json
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


DEFAULT_CONFIG = Path(__file__).with_name("template_config.json")


class TemplateError(ValueError):
    pass


def load_config(path):
    config_path = Path(path).expanduser().resolve()
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TemplateError(f"config does not exist: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise TemplateError(f"config is not valid JSON: {exc}") from exc
    validate_config(config)
    return config, config_path.parent


def require_mapping(config, key):
    value = config.get(key)
    if not isinstance(value, dict):
        raise TemplateError(f"{key} must be an object")
    return value


def require_text(mapping, key):
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TemplateError(f"{key} must be non-empty text")
    return value


def require_positive_number(mapping, key):
    value = mapping.get(key)
    if not isinstance(value, (int, float)) or value <= 0:
        raise TemplateError(f"{key} must be a positive number")
    return float(value)


def validate_config(config):
    if not isinstance(config, dict):
        raise TemplateError("config must be an object")
    identity = require_mapping(config, "identity")
    for key in ("title", "presenter", "team", "pdf_author"):
        require_text(identity, key)
    page = require_mapping(config, "page")
    for key in ("width", "height"):
        require_positive_number(page, key)
    layout = require_mapping(config, "layout")
    for key in (
        "card_margin",
        "card_radius",
        "card_padding",
        "grid_step",
        "logo_height",
    ):
        require_positive_number(layout, key)
    colors = require_mapping(config, "colors")
    for key in (
        "canvas_background",
        "grid_line",
        "card_background",
        "card_edge",
        "accent",
        "rule",
        "footer",
    ):
        try:
            HexColor(require_text(colors, key))
        except Exception as exc:
            raise TemplateError(f"{key} must be a valid color") from exc
    require_mapping(config, "fonts")
    require_mapping(config, "assets")


def resolve_optional_path(value, base_directory, label):
    if value in (None, ""):
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_directory / path
    path = path.resolve()
    if not path.is_file():
        raise TemplateError(f"{label} does not exist: {path}")
    return path


def register_fonts(config, base_directory):
    fonts = config["fonts"]
    regular_path = resolve_optional_path(
        fonts.get("regular_path"), base_directory, "regular font"
    )
    bold_path = resolve_optional_path(
        fonts.get("bold_path"), base_directory, "bold font"
    )
    if regular_path is None and bold_path is None:
        return "Helvetica", "Helvetica-Bold"
    if regular_path is None or bold_path is None:
        raise TemplateError("regular font and bold font must be provided together")
    regular_name = "PresentationTemplateRegular"
    bold_name = "PresentationTemplateBold"
    try:
        pdfmetrics.registerFont(TTFont(regular_name, regular_path))
        pdfmetrics.registerFont(TTFont(bold_name, bold_path))
    except Exception as exc:
        raise TemplateError(f"font could not be loaded: {exc}") from exc
    return regular_name, bold_name


def resolve_logo(config, base_directory, override):
    value = override if override is not None else config["assets"].get("logo_path")
    return resolve_optional_path(value, base_directory, "logo")


def draw_grid(pdf, width, height, step, background, line):
    pdf.setFillColor(background)
    pdf.rect(0, 0, width, height, stroke=0, fill=1)
    pdf.setStrokeColor(line)
    pdf.setLineWidth(0.6)
    x = 0.0
    while x <= width:
        pdf.line(x, 0, x, height)
        x += step
    y = 0.0
    while y <= height:
        pdf.line(0, y, width, y)
        y += step


def draw_card(pdf, width, height, margin, radius, background, edge):
    card = (margin, margin, width - 2 * margin, height - 2 * margin)
    pdf.setFillColor(background)
    pdf.setStrokeColor(edge)
    pdf.setLineWidth(2.4)
    pdf.roundRect(*card, radius, stroke=1, fill=1)
    return card


def draw_logo(pdf, logo, x, y, height, regular_font, rule_color):
    if logo is None:
        width = height * 4.9
        pdf.setStrokeColor(rule_color)
        pdf.setLineWidth(1)
        pdf.rect(x, y, width, height, stroke=1, fill=0)
        pdf.setFillColor(rule_color)
        pdf.setFont(regular_font, 12)
        pdf.drawCentredString(x + width / 2, y + height / 2 - 4, "LOGO")
        return
    try:
        image = ImageReader(str(logo))
        image_width, image_height = image.getSize()
        width = height * image_width / float(image_height)
        pdf.drawImage(
            image,
            x,
            y,
            width=width,
            height=height,
            preserveAspectRatio=True,
            mask="auto",
        )
    except Exception as exc:
        raise TemplateError(f"logo could not be loaded: {exc}") from exc


def draw_header(pdf, card, config, logo, regular_font, bold_font, colors):
    x, y, width, height = card
    layout = config["layout"]
    padding = float(layout["card_padding"])
    logo_height = float(layout["logo_height"])
    top = y + height - padding
    draw_logo(
        pdf,
        logo,
        x + padding,
        top - logo_height,
        logo_height,
        regular_font,
        colors["rule"],
    )
    pdf.setFillColor(colors["accent"])
    pdf.setFont(bold_font, 30)
    pdf.drawRightString(
        x + width - padding,
        top - logo_height + 9,
        config["identity"]["title"],
    )
    rule_y = top - logo_height - 22
    pdf.setStrokeColor(colors["rule"])
    pdf.setLineWidth(1.1)
    pdf.line(x + padding, rule_y, x + width - padding, rule_y)


def draw_footer(pdf, card, config, page_number, regular_font, colors):
    x, y, width, _ = card
    padding = float(config["layout"]["card_padding"])
    baseline = y + padding - 14
    pdf.setStrokeColor(colors["rule"])
    pdf.setLineWidth(1.1)
    pdf.line(x + padding, baseline + 20, x + width - padding, baseline + 20)
    pdf.setFillColor(colors["footer"])
    pdf.setFont(regular_font, 13)
    identity = config["identity"]
    footer = f"{identity['presenter']}  |  {identity['team']}"
    pdf.drawCentredString(x + width / 2, baseline, footer)
    pdf.drawRightString(x + width - padding, baseline, str(page_number))


def build(config_path, output, pages=1, logo_override=None):
    if pages < 1:
        raise TemplateError("pages must be at least 1")
    config, base_directory = load_config(config_path)
    regular_font, bold_font = register_fonts(config, base_directory)
    logo = resolve_logo(config, base_directory, logo_override)
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width = float(config["page"]["width"])
    height = float(config["page"]["height"])
    colors = {key: HexColor(value) for key, value in config["colors"].items()}
    layout = config["layout"]
    pdf = canvas.Canvas(str(output_path), pagesize=(width, height))
    pdf.setTitle(config["identity"]["title"])
    pdf.setAuthor(config["identity"]["pdf_author"])
    for page_number in range(1, pages + 1):
        draw_grid(
            pdf,
            width,
            height,
            float(layout["grid_step"]),
            colors["canvas_background"],
            colors["grid_line"],
        )
        card = draw_card(
            pdf,
            width,
            height,
            float(layout["card_margin"]),
            float(layout["card_radius"]),
            colors["card_background"],
            colors["card_edge"],
        )
        draw_header(
            pdf,
            card,
            config,
            logo,
            regular_font,
            bold_font,
            colors,
        )
        draw_footer(pdf, card, config, page_number, regular_font, colors)
        pdf.showPage()
    pdf.save()
    return output_path


def parse_arguments(arguments):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--output", default="presentation_template.pdf")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--logo")
    return parser, parser.parse_args(arguments)


def main(arguments=None):
    parser, args = parse_arguments(arguments)
    try:
        output = build(args.config, args.output, args.pages, args.logo)
    except TemplateError as exc:
        parser.error(str(exc))
    suffix = "page" if args.pages == 1 else "pages"
    print(f"{output} ({args.pages} {suffix})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
