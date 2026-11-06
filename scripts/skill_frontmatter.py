import re

FENCE = "---"
KEY_LINE = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z0-9_.-]+):(?:\s+(?P<value>.*))?$")
BLOCK_MARKERS = (">", ">-", ">+", "|", "|-", "|+")
DOUBLE_QUOTE_ESCAPE = re.compile(r"\\(.)")
ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


class FrontmatterError(ValueError):
    pass


def split_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() == FENCE:
            return lines[1:index], "\n".join(lines[index + 1:])
    raise FrontmatterError("unterminated frontmatter")


def indent_of(line):
    return len(line) - len(line.lstrip(" "))


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return DOUBLE_QUOTE_ESCAPE.sub(lambda m: ESCAPES.get(m.group(1), m.group(1)), value[1:-1])
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def scalar(value):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [scalar(item) for item in split_inline_list(inner)] if inner else []
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if value in ("null", "~"):
        return None
    return unquote(value)


def split_inline_list(inner):
    items, current, quote = [], "", None
    for char in inner:
        if quote:
            current += char
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
            current += char
        elif char == ",":
            items.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        items.append(current.strip())
    return items


def fold(lines):
    paragraphs, current = [], []
    for line in lines:
        if line.strip():
            current.append(line.strip())
        else:
            paragraphs.append(" ".join(current))
            current = []
    paragraphs.append(" ".join(current))
    return "\n".join(p for p in paragraphs if p)


def collect_more_indented(lines, start, parent_indent):
    taken = []
    index = start
    while index < len(lines):
        line = lines[index]
        if line.strip() and indent_of(line) <= parent_indent:
            break
        taken.append(line)
        index += 1
    while taken and not taken[-1].strip():
        taken.pop()
    return taken, index


def block_scalar(marker, lines):
    if marker.startswith(">"):
        return fold(lines)
    base = min((indent_of(l) for l in lines if l.strip()), default=0)
    text = "\n".join(l[base:] if l.strip() else "" for l in lines)
    return text if marker.endswith("-") else text + "\n"


def parse_mapping(lines, indent=0):
    result = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        match = KEY_LINE.match(line)
        if not match or len(match.group("indent")) != indent:
            raise FrontmatterError(f"unexpected line: {line!r}")
        key = match.group("key")
        value = (match.group("value") or "").strip()
        nested, index = collect_more_indented(lines, index + 1, indent)
        if value in BLOCK_MARKERS:
            result[key] = block_scalar(value, nested)
        elif value:
            result[key] = scalar(" ".join([value] + [n.strip() for n in nested if n.strip()])) if nested else scalar(value)
        elif nested and nested[0].lstrip().startswith("- "):
            result[key] = [scalar(n.strip()[2:]) for n in nested if n.strip().startswith("- ")]
        elif nested:
            result[key] = parse_mapping(nested, min(indent_of(n) for n in nested if n.strip()))
        else:
            result[key] = None
    return result


def parse_frontmatter(text):
    lines, _ = split_frontmatter(text)
    if lines is None:
        return {}
    return parse_mapping(lines)
