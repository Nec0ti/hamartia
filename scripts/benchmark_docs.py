#!/usr/bin/env python3
"""Offline structural and evidence-integrity checks for the bilingual wiki tasks.

This does not score human answers, fetch external links, render screenshots, or
contact an AI/provider. It parses the actual generated HTML shipped in docs/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import random
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TASKS_PATH = DOCS / "benchmark" / "tasks.json"
KEY_PATH = DOCS / "benchmark" / "answer_key.json"
DECOYS_PATH = DOCS / "benchmark" / "decoys.json"
PROTOCOL_PATH = DOCS / "benchmark" / "README.md"
CHECKER_PATH = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "reports" / "2026-11-15-docs-benchmark-results.json"
LOCALES = ("en", "tr")
EXPECTED_PAGE_COUNT = 17


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    parent: "Node | None" = None
    children: list["Node"] = field(default_factory=list)
    text: list[str] = field(default_factory=list)

    def descendants(self, tag: str | None = None):
        for child in self.children:
            if tag is None or child.tag == tag:
                yield child
            yield from child.descendants(tag)

    def own_text(self) -> str:
        return "".join(self.text)


class TreeParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self.stack = [self.root]
        self.ids: set[str] = set()
        self.duplicate_ids: list[str] = []
        self.sections: dict[str, list[str]] = {}
        self.active_section: str | None = None
        self.hrefs: list[str] = []
        self.srcs: list[str] = []
        self._section_chunks: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        node = Node(tag, attrs_dict, self.stack[-1])
        node.parent.children.append(node)
        element_id = attrs_dict.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.append(element_id)
            self.ids.add(element_id)
        if tag == "h2":
            self.active_section = element_id
            if element_id:
                self._section_chunks[element_id] = []
        if tag == "a" and "href" in attrs_dict:
            self.hrefs.append(attrs_dict["href"])
        if tag in {"img", "script", "source"} and "src" in attrs_dict:
            self.srcs.append(attrs_dict["src"])
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break
        if tag == "h2":
            # Section capture deliberately continues until the next h2.
            pass

    def handle_data(self, data: str) -> None:
        self.stack[-1].text.append(data)
        if self.active_section:
            self._section_chunks[self.active_section].append(data)

    def finish(self) -> None:
        self.sections = {key: chunks for key, chunks in self._section_chunks.items()}


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    return re.sub(r"\s+", " ", value).strip()


def markdown_section(content: str, heading: str) -> str | None:
    lines = content.splitlines()
    marker = f"## {heading}"
    for index, line in enumerate(lines):
        if line.strip() == marker:
            end = next((cursor for cursor in range(index + 1, len(lines)) if lines[cursor].startswith("## ")), len(lines))
            return "\n".join(lines[index + 1:end])
    return None


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest_entries(entries: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for relative_path, content in sorted(entries):
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def files_digest(paths: list[Path], base: Path) -> str:
    return digest_entries([(path.relative_to(base).as_posix(), path.read_bytes()) for path in paths])


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_hash_sensitivity(rendered_files: list[Path]) -> dict:
    """In-memory perturbations prove each tracked input affects its digest."""
    task_files = [TASKS_PATH, KEY_PATH, DECOYS_PATH]
    task_entries = [(path.relative_to(ROOT).as_posix(), path.read_bytes()) for path in task_files]
    original_task_digest = digest_entries(task_entries)
    for index, (relative_path, content) in enumerate(task_entries):
        changed = list(task_entries)
        changed[index] = (relative_path, content + b"\nbenchmark-hash-sensitivity-probe")
        if digest_entries(changed) == original_task_digest:
            raise ValueError(f"Task-pack digest ignored a changed input: {relative_path}")

    rendered_entries = [(path.relative_to(ROOT).as_posix(), path.read_bytes()) for path in rendered_files]
    original_rendered_digest = digest_entries(rendered_entries)
    for index, (relative_path, content) in enumerate(rendered_entries):
        changed = list(rendered_entries)
        changed[index] = (relative_path, content + b"\nbenchmark-hash-sensitivity-probe")
        if digest_entries(changed) == original_rendered_digest:
            raise ValueError(f"Rendered-wiki digest ignored a changed input: {relative_path}")

    for label, path in (("protocol", PROTOCOL_PATH), ("checker", CHECKER_PATH)):
        content = path.read_bytes()
        if file_sha256(path) == hashlib.sha256(content + b"\nbenchmark-hash-sensitivity-probe").hexdigest():
            raise ValueError(f"{label} digest ignored a changed file")
    return {
        "task_pack_members": len(task_files),
        "rendered_wiki_members": len(rendered_files),
        "protocol_files": 1,
        "checker_files": 1,
    }


def page_rel(path: Path) -> tuple[str, str]:
    rel = path.relative_to(DOCS).as_posix()
    parts = rel.split("/")
    if parts[0] == "tr":
        locale, page = "tr", parts[1] if len(parts) > 2 else "index"
    else:
        locale, page = "en", parts[0] if len(parts) > 1 else "index"
    if page == "index.html":
        page = "index"
    return locale, page


def route_from_href(current: Path, href: str) -> tuple[str | None, str | None, bool]:
    """Return (relative file, fragment, external); never performs network I/O."""
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc:
        return None, None, True
    raw_path = unquote(parsed.path)
    if raw_path.startswith("/"):
        raw_path = raw_path.lstrip("/")
    else:
        raw_path = posixpath.join(current.relative_to(DOCS).parent.as_posix(), raw_path)
    raw_path = posixpath.normpath(raw_path or current.relative_to(DOCS).as_posix())
    if raw_path == ".":
        raw_path = "index.html"
    if raw_path.endswith("/"):
        raw_path += "index.html"
    elif not posixpath.splitext(raw_path)[1]:
        raw_path = posixpath.join(raw_path, "index.html")
    if raw_path.startswith("../") or raw_path == "..":
        return raw_path, unquote(parsed.fragment) or None, False
    return raw_path, unquote(parsed.fragment) or None, False


def link_target_page(rel_file: str) -> tuple[str, str] | None:
    if rel_file == "index.html":
        return "en", "index"
    if rel_file == "tr/index.html":
        return "tr", "index"
    parts = rel_file.split("/")
    if len(parts) == 3 and parts[0] == "tr" and parts[2] == "index.html":
        return "tr", parts[1]
    if len(parts) == 2 and parts[1] == "index.html":
        return "en", parts[0]
    return None


def nav_targets(parser: TreeParser) -> tuple[list[str], list[Node], int]:
    navs = [node for node in parser.root.descendants("nav") if "documentation" in node.attrs.get("aria-label", "").casefold() or "dokümantasyon" in node.attrs.get("aria-label", "").casefold()]
    if len(navs) != 1:
        return [], [], len(navs)
    targets = []
    for anchor in navs[0].descendants("a"):
        href = anchor.attrs.get("href", "")
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc:
            targets.append("EXTERNAL")
            continue
        # Navigation links resolve from the source page; capture canonical route.
        targets.append(href)
    return targets, list(navs[0].descendants("a")), len(navs)


def run_integrity() -> dict:
    errors: list[str] = []
    pages: dict[tuple[str, str], tuple[Path, TreeParser]] = {}
    html_files = sorted(DOCS.glob("**/index.html"))
    for path in html_files:
        if path.is_relative_to(DOCS / "benchmark"):
            continue
        locale, page = page_rel(path)
        parser = TreeParser()
        parser.feed(path.read_text(encoding="utf-8"))
        parser.finish()
        pages[(locale, page)] = (path, parser)
        html_nodes = list(parser.root.descendants("html"))
        h1_nodes = list(parser.root.descendants("h1"))
        if len(html_nodes) != 1 or html_nodes[0].attrs.get("lang") != locale:
            errors.append(f"{path.relative_to(ROOT)}: expected one html lang={locale}")
        if len(h1_nodes) != 1:
            errors.append(f"{path.relative_to(ROOT)}: expected exactly one h1, got {len(h1_nodes)}")
        if parser.duplicate_ids:
            errors.append(f"{path.relative_to(ROOT)}: duplicate id(s): {sorted(set(parser.duplicate_ids))}")

    if len([key for key in pages if key[0] == "en"]) != EXPECTED_PAGE_COUNT:
        errors.append("English rendered route count is not 17")
    if len([key for key in pages if key[0] == "tr"]) != EXPECTED_PAGE_COUNT:
        errors.append("Turkish rendered route count is not 17")
    en_pages = {page for locale, page in pages if locale == "en"}
    tr_pages = {page for locale, page in pages if locale == "tr"}
    if en_pages != tr_pages:
        errors.append(f"Locale route sets differ: EN-only={sorted(en_pages-tr_pages)}, TR-only={sorted(tr_pages-en_pages)}")

    nav_order: dict[str, list[str]] = {}
    local_links = 0
    external_links = 0
    for (locale, page), (path, parser) in pages.items():
        nav_hrefs, nav_anchors, nav_count = nav_targets(parser)
        if nav_count != 1:
            errors.append(f"{path.relative_to(ROOT)}: expected exactly one documentation navigation, got {nav_count}")
        active_links = [node for node in nav_anchors if node.attrs.get("aria-current") == "page"]
        if len(active_links) != 1:
            errors.append(f"{path.relative_to(ROOT)}: expected one active navigation item, got {len(active_links)}")
        elif nav_count == 1:
            active_target, _, active_external = route_from_href(path, active_links[0].attrs.get("href", ""))
            if active_external or link_target_page(active_target or "") != (locale, page):
                errors.append(f"{path.relative_to(ROOT)}: active navigation item points to a different page")
        ids_from_nav = []
        for href in nav_hrefs:
            target, fragment, external = route_from_href(path, href)
            if external or target is None:
                errors.append(f"{path.relative_to(ROOT)}: unexpected external documentation nav link {href!r}")
                continue
            target_page = link_target_page(target)
            if target_page is None or target_page[0] != locale or target_page not in pages:
                errors.append(f"{path.relative_to(ROOT)}: nav route {href!r} is invalid or crosses locale")
                continue
            ids_from_nav.append(target_page[1])
        if len(ids_from_nav) != EXPECTED_PAGE_COUNT or len(set(ids_from_nav)) != EXPECTED_PAGE_COUNT:
            errors.append(f"{path.relative_to(ROOT)}: navigation must contain 17 unique routes")
        if page == "index":
            nav_order[locale] = ids_from_nav
            if not ids_from_nav or ids_from_nav[0] != "index":
                errors.append(f"{path.relative_to(ROOT)}: Getting Started must be first in navigation")

        anchors_current = parser.ids
        for href in parser.hrefs + parser.srcs:
            target, fragment, external = route_from_href(path, href)
            if external:
                external_links += 1
                parsed = urlsplit(href)
                if parsed.scheme in {"http", "https"} and not parsed.hostname:
                    errors.append(f"{path.relative_to(ROOT)}: malformed external URL {href!r}")
                continue
            local_links += 1
            if target is None or target.startswith("../") or target == "..":
                errors.append(f"{path.relative_to(ROOT)}: local link escapes docs root: {href!r}")
                continue
            target_path = DOCS / target
            if not target_path.is_file():
                errors.append(f"{path.relative_to(ROOT)}: missing local target {href!r} -> {target}")
                continue
            if fragment:
                if target_path == path:
                    target_parser = parser
                else:
                    target_parser = TreeParser()
                    target_parser.feed(target_path.read_text(encoding="utf-8"))
                if fragment not in target_parser.ids:
                    errors.append(f"{path.relative_to(ROOT)}: missing local anchor {href!r} -> {target}#{fragment}")

        language_links = [node for node in parser.root.descendants("a") if "language-link" in node.attrs.get("class", "").split()]
        if len(language_links) != 1:
            errors.append(f"{path.relative_to(ROOT)}: expected one locale switch link")
        else:
            target, _, external = route_from_href(path, language_links[0].attrs.get("href", ""))
            expected_locale = "tr" if locale == "en" else "en"
            target_page = link_target_page(target) if target else None
            if external or target_page != (expected_locale, page) or target_page not in pages:
                errors.append(f"{path.relative_to(ROOT)}: locale switch does not target paired page")
    if nav_order.get("en") != nav_order.get("tr"):
        errors.append("English and Turkish navigation order differs")
    for page in en_pages & tr_pages:
        en_anchor_order = list(pages[("en", page)][1].sections)
        tr_anchor_order = list(pages[("tr", page)][1].sections)
        if en_anchor_order != tr_anchor_order:
            errors.append(f"EN/TR h2 anchor order differs for {page}")

    tasks = read_json(TASKS_PATH)
    key = read_json(KEY_PATH)
    decoys = read_json(DECOYS_PATH)
    if tasks.get("task_set_id") != key.get("task_set_id"):
        errors.append("Task workbook and answer key task_set_id differ")
    if tasks.get("version") != 1:
        errors.append("Task set version must be explicitly versioned as 1")
    scoring = key.get("scoring", {})
    if (scoring.get("points_per_task"), scoring.get("points_per_locale"), scoring.get("points_total")) != (5, 50, 100):
        errors.append("Rubric point totals must be five per task, 50 per locale, and 100 overall")
    if (scoring.get("minimum_total_percent"), scoring.get("minimum_each_locale_percent"), scoring.get("critical_tasks_require_full_credit")) != (90, 85, True):
        errors.append("Human gates must remain 90% overall, 85% per locale, and full credit on critical tasks")
    task_entries = tasks.get("tasks", [])
    key_entries = key.get("tasks", [])
    task_pairs: dict[str, set[str]] = {}
    task_localized_ids: set[tuple[str, str]] = set()
    ui_task_counts = {locale: 0 for locale in LOCALES}
    for task in task_entries:
        task_key = (task.get("id", ""), task.get("locale", ""))
        if task_key in task_localized_ids:
            errors.append(f"Duplicate task prompt: {task_key[0]}/{task_key[1]}")
        task_localized_ids.add(task_key)
        task_pairs.setdefault(task.get("id", ""), set()).add(task.get("locale", ""))
        if task.get("type") == "ui_task" and task.get("locale") in ui_task_counts:
            ui_task_counts[task["locale"]] += 1
        if not task.get("prompt", "").strip():
            errors.append(f"Task {task.get('id')!r}/{task.get('locale')!r} has no prompt")
    if len(task_pairs) != 10 or any(locales != set(LOCALES) for locales in task_pairs.values()):
        errors.append("Task corpus must contain 10 EN/TR paired prompts")
    if len(task_entries) != 20:
        errors.append(f"Expected 20 task prompts, got {len(task_entries)}")
    if any(count != 1 for count in ui_task_counts.values()):
        errors.append("Each locale must have exactly one fixed-viewport screenshot task")
    key_pairs: dict[tuple[str, str], dict] = {}
    evidence_count = 0
    rendered_evidence_count = 0
    protocol_evidence_count = 0
    critical_ids = set()
    for entry in key_entries:
        ident, locale = entry.get("id"), entry.get("locale")
        if (ident, locale) in key_pairs:
            errors.append(f"Duplicate answer key entry: {ident}/{locale}")
        key_pairs[(ident, locale)] = entry
        if (ident, locale) not in task_localized_ids:
            errors.append(f"Answer key has no matching task prompt: {ident}/{locale}")
        if entry.get("critical"):
            critical_ids.add(ident)
        criteria = entry.get("criteria", [])
        if sum(c.get("points", 0) for c in criteria) != key.get("scoring", {}).get("points_per_task"):
            errors.append(f"Rubric points do not add to five: {ident}/{locale}")
        for criterion in criteria:
            if not criterion.get("evidence"):
                errors.append(f"Rubric criterion lacks evidence: {ident}/{locale}/{criterion.get('claim')}")
                continue
            for evidence in criterion["evidence"]:
                evidence_count += 1
                evidence_source = evidence.get("source", "rendered_page")
                quote = evidence.get("quote", "")
                if evidence_source == "human_protocol":
                    protocol_evidence_count += 1
                    file_path = (ROOT / evidence.get("file", "")).resolve()
                    if file_path != PROTOCOL_PATH.resolve():
                        errors.append(f"Human-protocol evidence must target {PROTOCOL_PATH.relative_to(ROOT)}")
                        continue
                    protocol_text = markdown_section(file_path.read_text(encoding="utf-8"), evidence.get("section", ""))
                    if protocol_text is None or not quote or normalized(quote) not in normalized(protocol_text):
                        errors.append(f"Human protocol excerpt missing from section {evidence.get('section')!r}: {quote!r}")
                    continue
                if evidence_source != "rendered_page":
                    errors.append(f"Unknown evidence source {evidence_source!r} for {ident}/{locale}")
                    continue
                rendered_evidence_count += 1
                target_locale = evidence.get("locale", locale)
                page = evidence.get("page", "")
                anchor = evidence.get("anchor", "")
                target_entry = pages.get((target_locale, page))
                if target_entry is None:
                    errors.append(f"Evidence route missing: {target_locale}/{page}#{anchor}")
                    continue
                _, target_parser = target_entry
                if anchor not in target_parser.sections:
                    errors.append(f"Evidence anchor missing or not an h2 section: {target_locale}/{page}#{anchor}")
                    continue
                section_text = normalized(" ".join(target_parser.sections[anchor]))
                if not quote or normalized(quote) not in section_text:
                    errors.append(f"Evidence excerpt not found in rendered target section: {target_locale}/{page}#{anchor}: {quote!r}")
    if len(key_entries) != 20 or len(key_pairs) != 20:
        errors.append("Answer key must contain 20 unique localized rubrics")
    if set(key_pairs) != task_localized_ids:
        errors.append("Answer-key entries do not exactly cover the localized task prompts")
    task_critical = {(task.get("id"), task.get("locale")) for task in task_entries if task.get("critical")}
    key_critical = {(ident, locale) for (ident, locale), entry in key_pairs.items() if entry.get("critical")}
    if task_critical != key_critical:
        errors.append("Critical gates differ between prompts and answer key")
    for locale in LOCALES:
        locale_total = sum(sum(c.get("points", 0) for c in entry.get("criteria", [])) for entry in key_entries if entry.get("locale") == locale)
        if locale_total != key.get("scoring", {}).get("points_per_locale"):
            errors.append(f"{locale} rubric total should be 50, got {locale_total}")
    if sum(sum(c.get("points", 0) for c in entry.get("criteria", [])) for entry in key_entries) != key.get("scoring", {}).get("points_total"):
        errors.append("Overall rubric score should total 100")

    decoy_entries = decoys.get("fixtures", [])
    all_prompts = "\n".join(task.get("prompt", "") for task in task_entries)
    for decoy in decoy_entries:
        target = decoy.get("target", "")
        kind = decoy.get("kind")
        if kind == "broken_local_route":
            rel_target = target.removeprefix("docs/")
            if (DOCS / rel_target).exists():
                errors.append(f"Expected synthetic broken route exists: {target}")
            prompt_route = target.removeprefix("docs/").removesuffix("index.html")
            if prompt_route not in all_prompts:
                errors.append(f"Broken-route decoy is not mentioned in task prompts: {target}")
        elif kind == "broken_local_anchor":
            route, _, anchor = target.partition("#")
            rel_target = route.removeprefix("docs/")
            target_path = DOCS / rel_target
            parser = TreeParser()
            if target_path.is_file():
                parser.feed(target_path.read_text(encoding="utf-8"))
                if anchor in parser.ids:
                    errors.append(f"Expected synthetic broken anchor exists: {target}")
            else:
                errors.append(f"Broken-anchor fixture route unexpectedly absent: {target}")
            prompt_anchor = target.removeprefix("docs/").replace("/index.html#", "/#")
            if prompt_anchor not in all_prompts:
                errors.append(f"Broken-anchor decoy is not mentioned in task prompts: {target}")
        elif kind == "synthetic_external_stale_link":
            if urlsplit(target).hostname != "example.invalid":
                errors.append(f"Stale external fixture must use reserved example.invalid host: {target}")
            if target.removeprefix("https://") not in all_prompts:
                errors.append(f"Stale-link decoy is not mentioned in task prompts: {target}")
        else:
            errors.append(f"Unknown decoy kind: {kind!r}")

    if errors:
        raise ValueError("\n".join(errors))
    rendered_files = [path for path in DOCS.rglob("*") if path.is_file() and "benchmark" not in path.relative_to(DOCS).parts]
    hash_sensitivity = verify_hash_sensitivity(rendered_files)
    return {
        "benchmark": "hamartia-bilingual-docs-integrity-v1",
        "task_set_id": tasks["task_set_id"],
        "task_pack_sha256": files_digest([TASKS_PATH, KEY_PATH, DECOYS_PATH], ROOT),
        "rendered_wiki_sha256": files_digest(rendered_files, ROOT),
        "protocol_sha256": file_sha256(PROTOCOL_PATH),
        "checker_sha256": file_sha256(CHECKER_PATH),
        "hash_sensitivity_self_checks": hash_sensitivity,
        "mode": "automated_integrity_only",
        "ai_included": False,
        "network_access": False,
        "rendered_pages": {"en": len(en_pages), "tr": len(tr_pages)},
        "nav_routes_per_locale": EXPECTED_PAGE_COUNT,
        "active_nav_items_checked": len(pages),
        "paired_h2_anchor_orders_checked": len(en_pages & tr_pages),
        "local_links_and_assets_checked": local_links,
        "external_links_syntactically_counted_not_fetched": external_links,
        "answer_rubrics_checked": len(key_entries),
        "exact_evidence_excerpts_checked": evidence_count,
        "rendered_section_excerpts_checked": rendered_evidence_count,
        "human_protocol_excerpts_checked": protocol_evidence_count,
        "synthetic_decoys_checked": len(decoy_entries),
        "task_prompts": len(task_entries),
        "critical_task_pairs": sorted(critical_ids),
        "human_task_runs": "pending",
        "fixed_viewport_screenshot_runs": "pending_manual",
        "errors": [],
    }


def make_booklet(locale: str, seed: int) -> dict:
    tasks = read_json(TASKS_PATH)
    selected = [task for task in tasks["tasks"] if task.get("locale") == locale]
    screenshot_tasks = [task for task in selected if task.get("type") == "ui_task"]
    retrieval_tasks = [task for task in selected if task.get("type") != "ui_task"]
    random.Random(seed).shuffle(retrieval_tasks)
    selected = retrieval_tasks + screenshot_tasks
    instructions = {
        "en": "Use the Hamartia wiki only. Cite page IDs and section anchors. Do not open external decoys or use AI/provider tools.",
        "tr": "Yalnızca Hamartia wiki'sini kullan. Sayfa kimliklerini ve bölüm bağlantılarını belirt. Sentetik dış bağlantıları açma; yapay zekâ veya sağlayıcı araçlarını kullanma.",
    }
    return {
        "task_set_id": tasks["task_set_id"],
        "locale": locale,
        "seed": seed,
        "ai_included": False,
        "instructions": instructions[locale],
        "tasks": [{"number": index + 1, "prompt": task["prompt"]} for index, task in enumerate(selected)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="write deterministic automated result JSON here")
    parser.add_argument("--booklet-locale", choices=LOCALES, help="emit one participant booklet without answer-key fields")
    parser.add_argument("--seed", type=int, help="required stable task order seed for --booklet-locale")
    args = parser.parse_args()
    if args.booklet_locale:
        if args.seed is None:
            parser.error("--seed is required with --booklet-locale")
        print(json.dumps(make_booklet(args.booklet_locale, args.seed), ensure_ascii=False, indent=2))
        return 0
    if args.seed is not None:
        parser.error("--seed can be used only with --booklet-locale")
    try:
        result = run_integrity()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Documentation benchmark integrity FAILED:\n{exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
