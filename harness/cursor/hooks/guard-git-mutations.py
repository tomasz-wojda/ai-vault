#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


MUTATION = re.compile(
    r"(?:^|(?:&&|\|\||[;|&])\s*)(?:sudo\s+)?"
    r"git(?:\s+-C\s+(?:\"[^\"]+\"|'[^']+'|\S+))?\s+"
    r"(?:--[^\s]+\s+)*(add|commit|push)\b"
)
GIT_C = re.compile(r"\bgit\s+-C\s+(\"[^\"]+\"|'[^']+'|\S+)")
CD = re.compile(r"(?:^|[;&|]\s*|&&\s*)cd\s+(\"[^\"]+\"|'[^']+'|[^;&|\s]+)")

MUTATING_ACTIONS = {"add", "commit", "push"}
SUBSTITUTION = "\0"
MAX_DEPTH = 8
COMMAND_SEPARATORS = {"\n", ";", "&", "|", "(", ")"}
TWO_CHARACTER_SEPARATORS = {"&&", "||", "|&", ";;"}
PREFIX_WORDS = {
    "!", "{", "}", "builtin", "command", "do", "elif", "else", "exec", "fi",
    "if", "nohup", "then", "time", "until", "while",
}
SHELLS = {"bash", "dash", "ksh", "sh", "zsh"}
SUDO_OPTIONS_WITH_VALUE = {"-C", "-D", "-g", "-h", "-p", "-r", "-t", "-U", "-u"}
XARGS_OPTIONS_WITH_VALUE = {"-a", "-d", "-E", "-I", "-L", "-n", "-P", "-s"}
GIT_OPTIONS_WITH_VALUE = {
    "-c", "--config-env", "--exec-path", "--git-dir", "--namespace",
    "--super-prefix", "--work-tree",
}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


class ParseError(Exception):
    pass


class Scanner:
    def __init__(self, text: str):
        self.text = text
        self.index = 0
        self.segments: list[list[str]] = []
        self.nested: list[str] = []
        self.words: list[str] = []
        self.word: list[str] = []
        self.in_word = False
        self.heredocs: list[tuple[str, bool, bool]] = []

    def scan(self) -> tuple[list[list[str]], list[str]]:
        text = self.text
        while self.index < len(text):
            character = text[self.index]
            following = text[self.index + 1] if self.index + 1 < len(text) else ""
            if character == "\\":
                if following == "\n":
                    self.index += 2
                    continue
                self.append(following)
                self.index += 2
            elif character == "'":
                end = text.find("'", self.index + 1)
                if end < 0:
                    raise ParseError("unterminated single quote")
                self.append(text[self.index + 1:end])
                self.index = end + 1
            elif character == '"':
                literal, nested, self.index = read_double_quoted(text, self.index)
                self.nested.extend(nested)
                self.append(literal)
            elif character == "`":
                content, self.index = read_backticks(text, self.index)
                self.nested.append(content)
                self.append(SUBSTITUTION)
            elif character == "$":
                self.read_dollar(following)
            elif character in "<>" and following == "(":
                content, self.index = read_balanced(text, self.index + 1)
                self.nested.append(content)
                self.append(SUBSTITUTION)
            elif character == "<" and following == "<":
                self.read_heredoc_operator()
            elif character in "<>" or (character == "&" and following == ">"):
                self.end_word()
                self.index += 1
                while self.index < len(text) and text[self.index] in "<>&|":
                    self.index += 1
            elif character in " \t":
                self.end_word()
                self.index += 1
            elif character == "#" and not self.in_word:
                end = text.find("\n", self.index)
                self.index = len(text) if end < 0 else end
            elif character in COMMAND_SEPARATORS:
                self.end_segment()
                pair = text[self.index:self.index + 2]
                self.index += 2 if pair in TWO_CHARACTER_SEPARATORS else 1
                if character == "\n":
                    self.read_heredoc_bodies()
            else:
                self.append(character)
                self.index += 1
        self.end_segment()
        return self.segments, self.nested

    def append(self, value: str) -> None:
        self.word.append(value)
        self.in_word = True

    def end_word(self) -> None:
        if self.in_word:
            self.words.append("".join(self.word))
        self.word = []
        self.in_word = False

    def end_segment(self) -> None:
        self.end_word()
        if self.words:
            self.segments.append(self.words)
        self.words = []

    def read_dollar(self, following: str) -> None:
        text = self.text
        if following == "(":
            content, self.index = read_balanced(text, self.index + 1)
            self.nested.append(content)
            self.append(SUBSTITUTION)
        elif following == "'":
            literal, self.index = read_ansi_c(text, self.index + 1)
            self.append(literal)
        elif following == "{":
            end = text.find("}", self.index + 2)
            if end < 0:
                raise ParseError("unterminated parameter expansion")
            self.append(SUBSTITUTION)
            self.index = end + 1
        else:
            self.append("$")
            self.index += 1

    def read_heredoc_operator(self) -> None:
        text = self.text
        self.end_word()
        if text.startswith("<<<", self.index):
            self.index += 3
            return
        self.index += 2
        strip_tabs = text.startswith("-", self.index)
        if strip_tabs:
            self.index += 1
        while self.index < len(text) and text[self.index] in " \t":
            self.index += 1
        start = self.index
        while self.index < len(text) and text[self.index] not in " \t\n;&|<>()":
            if text[self.index] in "'\"":
                end = text.find(text[self.index], self.index + 1)
                if end < 0:
                    raise ParseError("unterminated heredoc delimiter")
                self.index = end + 1
            else:
                self.index += 1
        raw = text[start:self.index]
        if not raw:
            raise ParseError("missing heredoc delimiter")
        quoted = any(character in raw for character in "'\"\\")
        delimiter = raw.replace("'", "").replace('"', "").replace("\\", "")
        self.heredocs.append((delimiter, quoted, strip_tabs))

    def read_heredoc_bodies(self) -> None:
        text = self.text
        for delimiter, quoted, strip_tabs in self.heredocs:
            lines: list[str] = []
            while self.index < len(text):
                end = text.find("\n", self.index)
                line_end = len(text) if end < 0 else end
                line = text[self.index:line_end]
                self.index = len(text) if end < 0 else end + 1
                candidate = line.lstrip("\t") if strip_tabs else line
                if candidate == delimiter:
                    break
                lines.append(line)
            if not quoted:
                self.nested.extend(substitutions("\n".join(lines)))
        self.heredocs = []


def read_balanced(text: str, start: int) -> tuple[str, int]:
    depth = 0
    index = start
    while index < len(text):
        character = text[index]
        if character == "\\":
            index += 2
            continue
        if character == "'":
            end = text.find("'", index + 1)
            if end < 0:
                raise ParseError("unterminated single quote")
            index = end + 1
            continue
        if character == '"':
            _, _, index = read_double_quoted(text, index)
            continue
        if character == "`":
            _, index = read_backticks(text, index)
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
        index += 1
    raise ParseError("unterminated substitution")


def read_double_quoted(text: str, start: int) -> tuple[str, list[str], int]:
    literal: list[str] = []
    nested: list[str] = []
    index = start + 1
    while index < len(text):
        character = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if character == '"':
            return "".join(literal), nested, index + 1
        if character == "\\" and following in '$`"\\\n':
            if following != "\n":
                literal.append(following)
            index += 2
        elif character == "$" and following == "(":
            content, index = read_balanced(text, index + 1)
            nested.append(content)
            literal.append(SUBSTITUTION)
        elif character == "`":
            content, index = read_backticks(text, index)
            nested.append(content)
            literal.append(SUBSTITUTION)
        else:
            literal.append(character)
            index += 1
    raise ParseError("unterminated double quote")


def read_backticks(text: str, start: int) -> tuple[str, int]:
    content: list[str] = []
    index = start + 1
    while index < len(text):
        character = text[index]
        if character == "\\" and index + 1 < len(text):
            content.append(text[index + 1])
            index += 2
            continue
        if character == "`":
            return "".join(content), index + 1
        content.append(character)
        index += 1
    raise ParseError("unterminated backtick")


def read_ansi_c(text: str, start: int) -> tuple[str, int]:
    index = start + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == "'":
            return text[start + 1:index], index + 1
        index += 1
    raise ParseError("unterminated ANSI-C quote")


def substitutions(text: str) -> list[str]:
    found: list[str] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character == "\\":
            index += 2
        elif character == "$" and text.startswith("(", index + 1):
            content, index = read_balanced(text, index + 1)
            found.append(content)
        elif character == "`":
            content, index = read_backticks(text, index)
            found.append(content)
        else:
            index += 1
    return found


def command_words(words: list[str]) -> list[str]:
    index = 0
    while index < len(words):
        word = words[index]
        if ASSIGNMENT.match(word) or word in PREFIX_WORDS:
            index += 1
        elif word == "env":
            index += 1
            while index < len(words) and (
                words[index].startswith("-") or ASSIGNMENT.match(words[index])
            ):
                index += 2 if words[index] in {"-u", "-C", "-S"} else 1
        elif word == "sudo":
            index += 1
            while index < len(words) and words[index].startswith("-"):
                index += 2 if words[index] in SUDO_OPTIONS_WITH_VALUE else 1
        elif word == "xargs":
            index += 1
            while index < len(words) and words[index].startswith("-"):
                index += 2 if words[index] in XARGS_OPTIONS_WITH_VALUE else 1
        else:
            break
    return words[index:]


def analyze_segment(
    words: list[str],
) -> tuple[tuple[str, list[str]] | None, list[str]]:
    words = command_words(words)
    if not words:
        return None, []
    program = os.path.basename(words[0])
    if program in SHELLS:
        for position, word in enumerate(words[1:], 1):
            if word.startswith("-") and not word.startswith("--") and "c" in word:
                if position + 1 < len(words):
                    return None, [words[position + 1]]
        return None, []
    if program == "eval":
        return None, [" ".join(words[1:])]
    if program != "git":
        return None, []
    index = 1
    git_c_paths: list[str] = []
    while index < len(words) and words[index].startswith("-"):
        option = words[index]
        if option == "-C" and index + 1 < len(words):
            git_c_paths.append(words[index + 1])
            index += 2
        elif option in GIT_OPTIONS_WITH_VALUE:
            index += 2
        else:
            index += 1
    if index < len(words) and words[index] in MUTATING_ACTIONS:
        return (words[index], git_c_paths), []
    return None, []


def find_mutations(
    command: str,
    depth: int = 0,
) -> tuple[list[tuple[str, list[str]]], list[str]]:
    if depth > MAX_DEPTH:
        raise ParseError("command nesting is too deep")
    segments, nested = Scanner(command).scan()
    mutations: list[tuple[str, list[str]]] = []
    cd_paths: list[str] = []
    for words in segments:
        effective = command_words(words)
        if effective[:1] == ["cd"] and len(effective) > 1:
            cd_paths.append(effective[1])
        mutation, scripts = analyze_segment(words)
        if mutation:
            mutations.append(mutation)
        nested.extend(scripts)
    for script in nested:
        inner_mutations, inner_cd_paths = find_mutations(script, depth + 1)
        mutations.extend(inner_mutations)
        cd_paths.extend(inner_cd_paths)
    return mutations, cd_paths


def unquote(value: str) -> str:
    try:
        values = shlex.split(value)
    except ValueError:
        return value.strip("'\"")
    return values[0] if values else ""


def git_root(path: Path) -> Path | None:
    try:
        output = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError:
        return None
    return Path(output.stdout.decode("utf-8").strip()).resolve()


def resolve(value: str, cwd: Path) -> Path:
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else cwd / candidate


def target_paths(command: str, cwd: Path) -> list[Path]:
    paths = [cwd]
    for match in GIT_C.finditer(command):
        paths.append(resolve(unquote(match.group(1)), cwd))
    for match in CD.finditer(command):
        paths.append(resolve(unquote(match.group(1)), cwd))
    return paths


def resolves_to_git_repo(path: Path) -> bool:
    return git_root(path) is not None


def is_unresolved(value: str) -> bool:
    return SUBSTITUTION in value or "$" in value or "`" in value


def blocked_action(command: str, cwd: Path) -> str | None:
    try:
        mutations, cd_paths = find_mutations(command)
    except ParseError:
        mutation = MUTATION.search(command)
        if not mutation:
            return None
        if any(resolves_to_git_repo(path) for path in target_paths(command, cwd)):
            return mutation.group(1)
        return None
    for action, git_c_paths in mutations:
        values = [*cd_paths, *git_c_paths]
        if any(is_unresolved(value) for value in values):
            return action
        paths = [cwd, *(resolve(value, cwd) for value in values)]
        if any(resolves_to_git_repo(path) for path in paths):
            return action
    return None


def main() -> int:
    payload = json.load(sys.stdin)
    command = payload.get("command", "")
    cwd = Path(payload.get("cwd") or ".").resolve()
    action = blocked_action(command, cwd)
    if action is None:
        print(json.dumps({"permission": "allow"}))
        return 0
    print(
        json.dumps(
            {
                "permission": "deny",
                "user_message": (
                    f"Agent-issued git {action} is blocked for Git repositories. "
                    "Use the two-command handoff."
                ),
                "agent_message": (
                    "Do not mutate Git state directly. Run read-only checks, "
                    "then render and provide the required commands."
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
