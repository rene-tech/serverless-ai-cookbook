"""Lexical MDL dependency evidence; this is not an MDL compiler or fetcher.

Only declared relative paths determine URL candidates. Search-root imports need
caller-supplied mappings; builtin names need existing path/SHA256 provenance.
Unknown external-looking strings and unresolved resource expressions fail closed.
MDL resource constructors and versioned path rules follow NVIDIA's language
specification: https://raytracing-docs.nvidia.com/mdl/specification/MDL_spec_1.10.2_14Mar2025.pdf
"""

from collections import namedtuple
import hashlib
import re
from urllib.parse import quote, urljoin, urlsplit

Token = namedtuple("Token", "kind value raw line start end")
RESOURCE_TYPES = {"texture_2d", "texture_3d", "texture_cube", "texture_ptex",
                  "light_profile", "bsdf_measurement"}
EXTERNAL = re.compile(r"^(?:\.{0,2}/|https?://|[A-Za-z]:[\\/])|\.(?:png|jpe?g|exr|hdr|dds|tiff?|bmp|tga|webp|ptx|ptex|ies|mbsdf|mdl)(?:[?#].*)?$", re.I)
TEXT_ANNOTATIONS = {"description", "display_name", "author", "contributor",
                    "copyright_notice", "created", "modified", "key_words",
                    "origin", "in_group", "enable_if"}


class MDLDependencyError(ValueError):
    """An external dependency cannot be resolved from the supplied evidence."""


def _fail(message, token=None):
    suffix = f" at line {token.line}: {token.raw}" if token else ""
    raise MDLDependencyError(message + suffix)


def _string(raw, line):
    result, index = [], 1
    simple = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r",
              "t": "\t", "v": "\v", "\\": "\\", '"': '"', "'": "'", "?": "?"}
    while index < len(raw) - 1:
        char = raw[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue
        index += 1
        escape = raw[index]
        if escape in simple:
            result.append(simple[escape]); index += 1
        elif escape in "uUx":
            count = {"u": 4, "U": 8}.get(escape)
            pattern = r"[0-9a-fA-F]{%d}" % count if count else r"[0-9a-fA-F]+"
            match = re.match(pattern, raw[index + 1:-1])
            if not match:
                raise MDLDependencyError(f"Invalid string escape at line {line}")
            value = int(match[0], 16)
            if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
                raise MDLDependencyError(f"Invalid Unicode escape at line {line}")
            result.append(chr(value)); index += 1 + len(match[0])
        elif escape in "01234567":
            match = re.match(r"[0-7]{1,3}", raw[index:-1])
            result.append(chr(int(match[0], 8))); index += len(match[0])
        else:
            raise MDLDependencyError(f"Unclassified string escape \\{escape} at line {line}")
    return "".join(result)


def _tokens(source):
    result, index, line = [], 0, 1
    while index < len(source):
        start, first_line = index, line
        if source[index].isspace():
            line += source[index] == "\n"; index += 1; continue
        if source.startswith("//", index):
            end = source.find("\n", index)
            index = len(source) if end < 0 else end
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                raise MDLDependencyError(f"Unterminated comment at line {line}")
            line += source[index:end + 2].count("\n"); index = end + 2
            continue
        if source[index] == '"':
            index += 1
            while index < len(source):
                if source[index] in "\n\r":
                    raise MDLDependencyError(f"Unterminated string at line {first_line}")
                if source[index] == '"':
                    index += 1; break
                index += 2 if source[index] == "\\" else 1
            else:
                raise MDLDependencyError(f"Unterminated string at line {first_line}")
            raw = source[start:index]
            result.append(Token("string", _string(raw, first_line), raw, first_line, start, index))
            continue
        match = re.match(r"[A-Za-z_][A-Za-z_0-9]*|[0-9]+|::|\.\.", source[index:])
        raw = match[0] if match else source[index]
        index += len(raw)
        kind = "identifier" if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", raw) else "punctuation"
        result.append(Token(kind, raw, raw, first_line, start, index))
    return result


def _url(value, label):
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise MDLDependencyError(f"{label} needs an explicit HTTP(S) URL without embedded credentials")
    return value


def _evidence(source, tokens, start, end):
    first, last = tokens[start], tokens[end - 1]
    return {"line": first.line, "raw": source[first.start:last.end],
            "character_offset": first.start}


def extract_dependencies(source, *, source_url, builtin_material_provenance,
                         module_urls=None, resource_root_url=None):
    """Return required/optional/builtin evidence, or raise on ambiguity.

    module_urls maps exact MDL module names (e.g. ::package::material) to
    authorized source URLs. resource_root_url is an explicit MDL search root,
    never inferred from the source host. No files or URLs are opened here.
    """
    _url(source_url, "source_url")
    module_urls = module_urls or {}
    tokens = _tokens(source)
    result = {"schema": "isaac-mdl-dependencies/v1", "source_url": source_url,
              "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
              "required": [], "optional": [], "builtins": [], "literals": [],
              "scope": "Lexical declarations only; compilation and transitive closure remain separate."}
    # A quoted string containing "mdl 1.6;" is not a language declaration.
    header = " ".join(t.raw for t in tokens[:5] if t.kind != "string")
    version_match = re.fullmatch(r"mdl\s+(\d+)\s*\.\s*(\d+)\s*;", header)
    version = tuple(map(int, version_match.groups())) if version_match else None
    result["mdl_version"] = list(version) if version else None
    consumed = set()

    def module(name, evidence):
        if not re.fullmatch(r"(?:::|(?:\.{1,2}::)+)?[A-Za-z_][A-Za-z_0-9]*(?:::[A-Za-z_][A-Za-z_0-9]*)*", name):
            raise MDLDependencyError(f"Unclassified module path {name!r} at line {evidence['line']}")
        key = name.removeprefix("::").replace("::", "/") + ".mdl"
        provenance = builtin_material_provenance.get(key)
        # Relative modules cannot be reclassified as globally installed names.
        if not name.startswith(".") and provenance is not None:
            if (not isinstance(provenance, dict) or not isinstance(provenance.get("path"), str)
                    or not provenance["path"] or not re.fullmatch(r"[0-9a-f]{64}", provenance.get("sha256", ""))):
                raise MDLDependencyError(f"Builtin {key} lacks exact installed path/SHA256 provenance")
            result["builtins"].append({"kind": "module", "module": name, "module_file": key,
                                       "provenance": dict(provenance), **evidence})
            return
        if name in module_urls:
            target, resolution = _url(module_urls[name], "module mapping"), "explicit-module-mapping"
        elif name.startswith("."):
            parts = name.split("::")
            target = urljoin(source_url, "/".join(parts) + ".mdl")
            resolution = "declared-relative-module"
        elif not name.startswith("::") and version is not None and version >= (1, 6):
            target = urljoin(source_url, key); resolution = "versioned-relative-module"
        else:
            raise MDLDependencyError(f"Module {name!r} needs exact builtin provenance or an explicit module URL at line {evidence['line']}")
        result["required"].append({"kind": "module", "module": name, "url": target,
                                    "resolution": resolution, **evidence})

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind != "identifier" or token.value not in {"using", "import"}:
            index += 1; continue
        end = next((i for i in range(index + 1, len(tokens))
                    if tokens[i].kind == "punctuation" and tokens[i].value == ";"), None)
        if end is None:
            _fail("Unterminated module declaration", token)
        clause = tokens[index + 1:end]
        evidence = _evidence(source, tokens, index, end + 1)
        if token.value == "using":
            split = next((i for i, t in enumerate(clause) if t.value == "import"), None)
            if split is None:
                _fail("Module alias requires explicit compiler/module resolution", token)
            module("".join(t.value for t in clause[:split]), evidence)
        else:
            groups, group = [], []
            for part in clause:
                if part.value == ",":
                    groups.append(group); group = []
                else:
                    group.append(part)
            groups.append(group)
            for group in groups:
                joined = "".join(t.value for t in group)
                if "::" not in joined.removeprefix("::"):
                    _fail("Import does not identify a module and symbol", token)
                module(joined.rsplit("::", 1)[0], evidence)
        consumed.update(range(index, end + 1)); index = end + 1

    pairs, stack, calls, ancestors = {}, [], {}, {}
    for i, token in enumerate(tokens):
        if token.kind == "punctuation" and token.value in {"(", "[", "{"}:
            stack.append(i)
            if token.value == "(":
                j = i - 1
                if j >= 0 and tokens[j].kind == "identifier":
                    while j >= 2 and tokens[j - 1].value == "::" and tokens[j - 2].kind == "identifier":
                        j -= 2
                    if j >= 1 and tokens[j - 1].value == "::":
                        j -= 1
                    calls[i] = "".join(t.value for t in tokens[j:i])
                else:
                    calls[i] = ""
        elif token.kind == "punctuation" and token.value in {")", "]", "}"}:
            if not stack or tokens[stack[-1]].value != {")": "(", "]": "[", "}": "{"}[token.value]:
                _fail("Unbalanced MDL delimiters", token)
            pairs[stack.pop()] = i
        if token.kind == "string":
            ancestors[i] = [calls[p] for p in stack if p in calls]
    if stack:
        _fail("Unclosed MDL delimiter", tokens[stack[-1]])

    def arguments(begin, end):
        groups, start, i = [], begin + 1, begin + 1
        while i < end:
            if i in pairs:
                i = pairs[i] + 1; continue
            if tokens[i].kind == "punctuation" and tokens[i].value == ",":
                groups.append(list(range(start, i))); start = i + 1
            i += 1
        if start < end:
            groups.append(list(range(start, end)))
        return groups

    for begin, name in calls.items():
        plain = name.removeprefix("::")
        thumbnail = plain == "anno::thumbnail"
        if plain not in RESOURCE_TYPES and not thumbnail:
            continue
        args = arguments(begin, pairs[begin])
        if not args:
            continue  # Empty resource constructor has no file dependency.
        named = [arg[2:] for arg in args if len(arg) > 2 and tokens[arg[0]].value == "name"
                 and tokens[arg[1]].value == ":"]
        selected = named[0] if len(named) == 1 else args[0] if not named else []
        if not selected or any(tokens[i].kind != "string" for i in selected):
            _fail("Resource name must be literal; type/compiler resolution is required", tokens[begin])
        literal = "".join(tokens[i].value for i in selected)
        consumed.update(selected)
        # A texture's selector names a channel inside its file, not another
        # resource. Do not swallow literals inside arbitrary nested calls.
        if plain in {"texture_2d", "texture_3d"}:
            for position, arg in enumerate(args):
                selector = arg[2:] if len(arg) > 2 and tokens[arg[0]].value == "selector" and tokens[arg[1]].value == ":" else arg if position == 2 and tokens[arg[0]].kind == "string" else []
                if selector and all(tokens[i].kind == "string" for i in selector):
                    consumed.update(selector)
        if not literal:
            continue
        if "\\" in literal or any(ord(char) < 32 for char in literal):
            _fail("Resource path cannot be mapped unambiguously", tokens[selected[0]])
        parsed = urlsplit(literal)
        if parsed.scheme:
            target, resolution = _url(literal, "resource"), "literal-url"
        elif literal.startswith("/"):
            if resource_root_url is None or literal.startswith("//"):
                _fail("Absolute MDL resource needs an explicit search root", tokens[selected[0]])
            target = urljoin(_url(resource_root_url, "resource root").rstrip("/") + "/",
                             quote(literal.lstrip("/"), safe="/%<>"))
            resolution = "explicit-resource-root"
        elif literal.startswith(("./", "../")) or (version is not None and version >= (1, 6)):
            target = urljoin(source_url, quote(literal, safe="/%<>"))
            resolution = "declared-relative-resource"
        else:
            _fail("Pre-1.6 weak relative resource requires compiler/search-path resolution", tokens[selected[0]])
        record = {"kind": "thumbnail" if thumbnail else "resource", "constructor": plain,
                  "reference": literal, "url": target, "resolution": resolution,
                  "pattern": bool(re.search(r"<UDIM>|<UVTILE[01]>|<\#+>", literal)),
                  **_evidence(source, tokens, selected[0], selected[-1] + 1)}
        result["optional" if thumbnail else "required"].append(record)

    for i, token in enumerate(tokens):
        if token.kind != "string":
            continue
        immediate_call = (ancestors.get(i) or [""])[-1]
        annotation = immediate_call.removeprefix("::") in {"anno::" + name for name in TEXT_ANNOTATIONS}
        if i not in consumed and not annotation and EXTERNAL.search(token.value):
            _fail("Unclassified external-looking string; explicit dependency evidence required", token)
        result["literals"].append({"value": token.value, "raw": token.raw, "line": token.line,
                                   "context": "resource-or-import" if i in consumed else "annotation" if annotation else "ordinary-string"})
    return result
