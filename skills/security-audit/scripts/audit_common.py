#!/usr/bin/env python3

from __future__ import annotations

import errno
import json
import math
import os
import re
import stat
import struct
import unicodedata
from bisect import bisect_right

MAX_DIAGNOSTIC_STRING_LENGTH = 256
VALIDATION_ERROR_LIMIT = 100
READ_CHUNK_BYTES = 64 * 1024
MAX_SAFE_INTEGER = 2**53 - 1
MAX_ARRAY_INDEX = 2**32 - 2

WHITE_SPACE = frozenset(
    chr(code)
    for code in (
        0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0x85, 0xA0, 0x1680,
        *range(0x2000, 0x200B),
        0x2028, 0x2029, 0x202F, 0x205F, 0x3000,
    )
)
JS_WHITESPACE = frozenset(
    chr(code)
    for code in (
        0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0xA0, 0x1680,
        *range(0x2000, 0x200B),
        0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF,
    )
)
JS_TRIM_CHARACTERS = "".join(sorted(JS_WHITESPACE))
DEFAULT_IGNORABLE_RANGES = (
    (0x00AD, 0x00AD),
    (0x034F, 0x034F),
    (0x061C, 0x061C),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180F),
    (0x200B, 0x200F),
    (0x202A, 0x202E),
    (0x2060, 0x206F),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFEFF, 0xFEFF),
    (0xFFA0, 0xFFA0),
    (0xFFF0, 0xFFF8),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
    (0xE0000, 0xE0FFF),
)
_IGNORABLE_STARTS = tuple(start for start, _ in DEFAULT_IGNORABLE_RANGES)
WINDOWS_RESERVED_COMPONENT = re.compile(
    r"^(?:con|prn|aux|nul|clock\$|conin\$|conout\$"
    r"|com[1-9\u00b9\u00b2\u00b3]|lpt[1-9\u00b9\u00b2\u00b3])(?:\.|\Z)",
    re.IGNORECASE,
)
_DRIVE_PREFIX = re.compile(r"[A-Za-z]:")
_ARRAY_INDEX = re.compile(r"0|[1-9][0-9]*")


class SafeInputError(Exception):
    pass


class JsonStructureError(Exception):
    pass


class _Undefined:
    __slots__ = ()

    def __repr__(self) -> str:
        return "undefined"

    def __bool__(self) -> bool:
        return False


UNDEFINED = _Undefined()


def js_get(value, key):
    if isinstance(value, dict) and key in value:
        return value[key]
    return UNDEFINED


def js_truthy(value) -> bool:
    if value is None or value is UNDEFINED or value is False:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return value != 0 and not (isinstance(value, float) and math.isnan(value))
    if isinstance(value, str):
        return value != ""
    return True


def type_of(value) -> str:
    if value is None:
        return "null"
    if value is UNDEFINED:
        return "undefined"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_float(value) -> float:
    try:
        return float(value)
    except OverflowError:
        return math.inf if value > 0 else -math.inf


def is_js_integer(value) -> bool:
    if not is_number(value):
        return False
    number = _as_float(value)
    return math.isfinite(number) and number.is_integer()


def is_finite_number(value) -> bool:
    return is_number(value) and math.isfinite(_as_float(value))


def _shortest_digits(number: float) -> tuple[str, int]:
    text = repr(abs(number))
    mantissa, _, exponent = text.partition("e")
    integer, _, fraction = mantissa.partition(".")
    digits = integer + fraction
    point = len(integer) + (int(exponent) if exponent else 0)
    stripped = digits.lstrip("0")
    point -= len(digits) - len(stripped)
    return stripped.rstrip("0"), point


def _js_float_text(number: float) -> str:
    if math.isnan(number):
        return "NaN"
    if math.isinf(number):
        return "Infinity" if number > 0 else "-Infinity"
    if number == 0:
        return "0"
    sign = "-" if number < 0 else ""
    digits, point = _shortest_digits(number)
    count = len(digits)
    if count <= point <= 21:
        body = digits + "0" * (point - count)
    elif 0 < point <= 21:
        body = digits[:point] + "." + digits[point:]
    elif -6 < point <= 0:
        body = "0." + "0" * (-point) + digits
    else:
        exponent = point - 1
        exponent_text = f"e{'+' if exponent >= 0 else '-'}{abs(exponent)}"
        body = digits[0] + ("." + digits[1:] if count > 1 else "") + exponent_text
    return sign + body


def js_number_text(value) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        if abs(value) <= MAX_SAFE_INTEGER:
            return str(value)
        return _js_float_text(_as_float(value))
    return _js_float_text(float(value))


def js_string(value: str) -> str:
    return value.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "surrogatepass")


def _utf16_units(value: str) -> tuple[int, ...]:
    data = value.encode("utf-16-le", "surrogatepass")
    return struct.unpack(f"<{len(data) // 2}H", data)


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le", "surrogatepass")) // 2


def utf16_key(value: str) -> bytes:
    return value.encode("utf-16-be", "surrogatepass")


def utf16_slice(value: str, limit: int) -> str:
    data = value.encode("utf-16-le", "surrogatepass")[: limit * 2]
    return data.decode("utf-16-le", "surrogatepass")


def utf8_length(value: str) -> int:
    return len(js_string(value).encode("utf-8", "surrogatepass"))


def code_point_length(value: str) -> int:
    units = _utf16_units(value)
    length = 0
    index = 0
    while index < len(units):
        first = units[index]
        index += 1
        if 0xD800 <= first <= 0xDBFF and index < len(units) and 0xDC00 <= units[index] <= 0xDFFF:
            index += 1
        length += 1
    return length


def has_valid_unicode_scalar_values(value: str) -> bool:
    units = _utf16_units(value)
    index = 0
    while index < len(units):
        first = units[index]
        index += 1
        if 0xD800 <= first <= 0xDBFF:
            if index >= len(units):
                return False
            second = units[index]
            index += 1
            if second < 0xDC00 or second > 0xDFFF:
                return False
        elif 0xDC00 <= first <= 0xDFFF:
            return False
    return True


def is_default_ignorable(character: str) -> bool:
    code = ord(character)
    position = bisect_right(_IGNORABLE_STARTS, code) - 1
    return position >= 0 and code <= DEFAULT_IGNORABLE_RANGES[position][1]


def is_visible_character(character: str) -> bool:
    if character in WHITE_SPACE:
        return False
    if unicodedata.category(character) in ("Cc", "Cf"):
        return False
    return not is_default_ignorable(character)


def has_visible_content(value: str) -> bool:
    return any(is_visible_character(character) for character in js_string(value))


def is_path_forbidden_character(character: str) -> bool:
    return unicodedata.category(character) in ("Cc", "Cf", "Zl", "Zp") or is_default_ignorable(character)


def has_path_forbidden_character(value: str) -> bool:
    return any(is_path_forbidden_character(character) for character in js_string(value))


def is_unsafe_diagnostic_character(character: str) -> bool:
    return unicodedata.category(character) in ("Cc", "Cf", "Cs", "Zl", "Zp") or is_default_ignorable(character)


def escape_unsafe_diagnostic_characters(value) -> str:
    text = js_string(value if isinstance(value, str) else str(value))
    parts = []
    for character in text:
        if is_unsafe_diagnostic_character(character):
            code = ord(character)
            parts.append(f"\\u{code:04x}" if code <= 0xFFFF else f"\\u{{{code:x}}}")
        else:
            parts.append(character)
    return "".join(parts)


def js_json_string(value: str) -> str:
    text = json.dumps(js_string(value), ensure_ascii=False)
    return "".join(
        f"\\u{ord(character):04x}" if 0xD800 <= ord(character) <= 0xDFFF else character
        for character in text
    )


def js_trim(value: str) -> str:
    return value.strip(JS_TRIM_CHARACTERS)


def js_keys(value: dict) -> list:
    indexes = []
    names = []
    for key in value:
        if _ARRAY_INDEX.fullmatch(key) and int(key) <= MAX_ARRAY_INDEX:
            indexes.append(key)
        else:
            names.append(key)
    return sorted(indexes, key=int) + names


def safe_quote(value) -> str:
    if isinstance(value, str):
        clipped = (
            utf16_slice(value, MAX_DIAGNOSTIC_STRING_LENGTH) + "..."
            if utf16_length(value) > MAX_DIAGNOSTIC_STRING_LENGTH
            else value
        )
        serialized = js_json_string(clipped)
    elif value is None:
        serialized = "null"
    elif isinstance(value, bool):
        serialized = "true" if value else "false"
    elif is_finite_number(value):
        serialized = js_number_text(value)
    else:
        serialized = f'"<{type_of(value)}>"'
    return escape_unsafe_diagnostic_characters(serialized)


class ErrorList(list):
    def __init__(self, limit: int = VALIDATION_ERROR_LIMIT):
        super().__init__()
        self.limit = limit

    def push(self, *messages) -> int:
        remaining = self.limit - len(self)
        if remaining > 0:
            self.extend(escape_unsafe_diagnostic_characters(message) for message in messages[:remaining])
        return len(self)


def has_visible_prose(value: str) -> bool:
    return has_valid_unicode_scalar_values(value) and has_visible_content(value)


def is_safe_relative_path(value) -> bool:
    if (
        not isinstance(value, str)
        or value == ""
        or not has_valid_unicode_scalar_values(value)
        or js_trim(value) != value
        or has_path_forbidden_character(value)
        or "\\" in value
        or ":" in value
    ):
        return False
    if value.startswith("/") or _DRIVE_PREFIX.match(value) or value.startswith("~"):
        return False
    return all(
        segment not in ("", ".", "..")
        and not segment.endswith((" ", "."))
        and not WINDOWS_RESERVED_COMPONENT.search(segment)
        for segment in value.split("/")
    )


def read_file_within_limit(path, max_bytes: int) -> str:
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    non_block = getattr(os, "O_NONBLOCK", 0)
    if not no_follow or not non_block:
        raise SafeInputError("OS no-follow and nonblocking input protection is unavailable")
    flags = os.O_RDONLY | no_follow | non_block | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.EMLINK):
            raise SafeInputError("input must not be a symlink") from None
        raise
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            raise SafeInputError("input must be a regular file")
        if status.st_size > max_bytes:
            raise SafeInputError(f"input exceeds {max_bytes} byte limit")
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise SafeInputError(f"input exceeds {max_bytes} byte limit")
            chunks.append(chunk)
        try:
            return b"".join(chunks).decode("utf-8")
        except UnicodeDecodeError:
            raise SafeInputError("input is not valid UTF-8") from None
    finally:
        os.close(descriptor)


def _reject_constant(name: str):
    raise ValueError(f"unsupported JSON constant {name}")


def parse_json_text(contents: str):
    return json.loads(contents, parse_constant=_reject_constant)
