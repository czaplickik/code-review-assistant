"""Minimal YAML subset loader (stdlib only).

Supported: block mappings and sequences (indentation based), sequences of mappings
("- key: value" with continuation lines), inline lists [a, b], inline maps {a: 1},
single/double quoted strings, plain scalars (int, float, bool, null), comments,
block scalars "|" and ">" (literal / folded). Not supported: anchors, tags, multi-docs.
"""
from __future__ import annotations

import re

__all__ = ["load", "loads", "YamlError"]


class YamlError(ValueError):
    pass


def load(path):
    with open(path, encoding="utf-8") as fh:
        return loads(fh.read(), source=str(path))


def loads(text, source="<string>"):
    lines = []
    for no, raw in enumerate(text.splitlines(), 1):
        if raw.strip() in ("---", "..."):
            continue
        lines.append((no, raw.rstrip("\n").replace("\t", "    ")))
    parser = _Parser(lines, source)
    value = parser.parse_block(0)
    parser.skip_blank()
    if parser.i < len(parser.lines):
        no, raw = parser.lines[parser.i]
        raise YamlError(f"{source}:{no}: unexpected content: {raw.strip()}")
    return {} if value is None else value


def _strip_comment(s):
    out, quote = [], None
    for idx, ch in enumerate(s):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (idx == 0 or s[idx - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _indent(s):
    return len(s) - len(s.lstrip(" "))


_KEY_RE = re.compile(r"""^(?P<key>"(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^:#\[\]{},][^:#]*?)\s*:(?:\s+|$)(?P<rest>.*)$""")


class _Parser:
    def __init__(self, lines, source):
        self.lines = lines
        self.i = 0
        self.source = source

    def err(self, msg):
        no = self.lines[min(self.i, len(self.lines) - 1)][0] if self.lines else 0
        raise YamlError(f"{self.source}:{no}: {msg}")

    def skip_blank(self):
        while self.i < len(self.lines) and not _strip_comment(self.lines[self.i][1]).strip():
            self.i += 1

    def peek(self):
        self.skip_blank()
        if self.i >= len(self.lines):
            return None
        raw = _strip_comment(self.lines[self.i][1])
        return _indent(raw), raw.strip()

    def parse_block(self, min_indent):
        nxt = self.peek()
        if nxt is None or nxt[0] < min_indent:
            return None
        ind, content = nxt
        if content.startswith("- ") or content == "-":
            return self.parse_seq(ind)
        return self.parse_map(ind)

    def parse_seq(self, ind):
        out = []
        while True:
            nxt = self.peek()
            if nxt is None or nxt[0] != ind or not (nxt[1].startswith("- ") or nxt[1] == "-"):
                if nxt is not None and nxt[0] > ind:
                    self.err("bad indentation in sequence")
                return out
            item = nxt[1][1:].strip()
            self.i += 1
            if not item:
                out.append(self.parse_block(ind + 1))
            elif _KEY_RE.match(item) and not item.startswith(("'", '"', "[", "{")):
                # mapping inside a sequence item: treat "- " as indentation
                child_ind = ind + 2
                self.i -= 1
                no, raw = self.lines[self.i]
                self.lines[self.i] = (no, " " * child_ind + item)
                out.append(self.parse_map(child_ind))
            else:
                out.append(self.parse_value_inline(item, ind))
        return out

    def parse_map(self, ind):
        out = {}
        while True:
            nxt = self.peek()
            if nxt is None or nxt[0] < ind:
                return out
            if nxt[0] > ind:
                self.err("bad indentation in mapping")
            content = nxt[1]
            if content.startswith("- "):
                return out
            m = _KEY_RE.match(content)
            if not m:
                self.err(f"expected 'key: value', got: {content}")
            key = _scalar(m.group("key"))
            rest = m.group("rest").strip()
            self.i += 1
            if rest == "":
                val = self.parse_block(ind + 1)
                # allow sequences at the same indentation as the key
                if val is None:
                    nxt2 = self.peek()
                    if nxt2 and nxt2[0] == ind and nxt2[1].startswith("- "):
                        val = self.parse_seq(ind)
                out[key] = val
            else:
                out[key] = self.parse_value_inline(rest, ind)

    def parse_value_inline(self, rest, ind):
        if rest in ("|", "|-", "|+", ">", ">-", ">+"):
            return self.parse_block_scalar(rest, ind)
        if rest.startswith("[") or rest.startswith("{"):
            text = rest
            while _unbalanced(text) and self.i < len(self.lines):
                text += " " + _strip_comment(self.lines[self.i][1]).strip()
                self.i += 1
            val, pos = _flow(text, 0)
            if text[pos:].strip():
                self.err(f"trailing content after flow value: {text[pos:]}")
            return val
        return _scalar(rest)

    def parse_block_scalar(self, style, ind):
        body, block_ind = [], None
        while self.i < len(self.lines):
            no, raw = self.lines[self.i]
            if raw.strip() == "":
                body.append("")
                self.i += 1
                continue
            cur = _indent(raw)
            if block_ind is None:
                if cur <= ind:
                    break
                block_ind = cur
            if cur < block_ind:
                break
            body.append(raw[block_ind:])
            self.i += 1
        while body and body[-1] == "":
            body.pop()
        if style.startswith(">"):
            paras, cur = [], []
            for line in body:
                if line == "":
                    paras.append(" ".join(cur))
                    cur = []
                else:
                    cur.append(line.strip())
            paras.append(" ".join(cur))
            text = "\n".join(paras)
        else:
            text = "\n".join(body)
        return text if style.endswith("-") else text + "\n"


def _unbalanced(text):
    depth, quote = 0, None
    for ch in text:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
    return depth > 0


def _flow(text, pos):
    pos = _ws(text, pos)
    ch = text[pos]
    if ch == "[":
        out, pos = [], pos + 1
        while True:
            pos = _ws(text, pos)
            if text[pos] == "]":
                return out, pos + 1
            val, pos = _flow(text, pos)
            out.append(val)
            pos = _ws(text, pos)
            if text[pos] == ",":
                pos += 1
            elif text[pos] != "]":
                raise YamlError(f"bad flow sequence: {text}")
    if ch == "{":
        out, pos = {}, pos + 1
        while True:
            pos = _ws(text, pos)
            if text[pos] == "}":
                return out, pos + 1
            key, pos = _flow_scalar(text, pos, stop=":")
            pos = _ws(text, pos)
            if text[pos] != ":":
                raise YamlError(f"bad flow mapping: {text}")
            val, pos = _flow(text, pos + 1)
            out[key] = val
            pos = _ws(text, pos)
            if text[pos] == ",":
                pos += 1
            elif text[pos] != "}":
                raise YamlError(f"bad flow mapping: {text}")
    return _flow_scalar(text, pos, stop=",]}")


def _flow_scalar(text, pos, stop):
    pos = _ws(text, pos)
    if text[pos] in "'\"":
        q = text[pos]
        end = pos + 1
        while end < len(text):
            if text[end] == q:
                if q == "'" and end + 1 < len(text) and text[end + 1] == "'":
                    end += 2
                    continue
                if q == '"' and text[end - 1] == "\\":
                    end += 1
                    continue
                break
            end += 1
        return _scalar(text[pos:end + 1]), end + 1
    end = pos
    while end < len(text) and text[end] not in stop:
        end += 1
    return _scalar(text[pos:end].strip()), end


def _ws(text, pos):
    while pos < len(text) and text[pos] in " \t":
        pos += 1
    return pos


_INT = re.compile(r"^[-+]?\d+$")
_FLOAT = re.compile(r"^[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?$")


def _scalar(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] == "'":
        return s[1:-1].replace("''", "'")
    if len(s) >= 2 and s[0] == s[-1] == '"':
        return bytes(s[1:-1], "utf-8").decode("unicode_escape") if "\\" in s else s[1:-1]
    low = s.lower()
    if low in ("", "~", "null"):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if _INT.match(s):
        return int(s)
    if _FLOAT.match(s):
        return float(s)
    return s
