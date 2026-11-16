"""Generate sequential ARETE codes and bilingual GitHub release notes."""

import argparse
import base64
import html
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


TAG_PATTERN = re.compile(r"^ARETE-(\d+)$")
REQUIRED_ASSET_SUFFIXES = {".exe", ".deb", ".appimage"}
RELEASE_SUMMARY_START = "<!-- release-summary:start -->"
RELEASE_SUMMARY_END = "<!-- release-summary:end -->"
RELEASE_SUMMARY_FIELDS = (
    "Highlights",
    "Behavior and why",
    "How to use",
    "Compatibility / migration",
    "Verification",
    "Not run / known limitations",
)
TURKISH_RELEASE_FIELDS = {
    "Highlights": "Öne çıkanlar",
    "Behavior and why": "Davranış ve nedeni",
    "How to use": "Kullanım",
    "Compatibility / migration": "Uyumluluk / geçiş",
    "Verification": "Doğrulama",
    "Not run / known limitations": "Çalıştırılmayanlar / bilinen sınırlamalar",
}
MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+.!|>~\-/:])")


def safe_release_text(value, allow_lists=False):
    lines = []
    for line in value.splitlines():
        if not line.strip():
            lines.append("")
            continue
        prefix = ""
        if allow_lists:
            bullet = re.match(r"^\s*[-*+]\s+(.*)$", line)
            ordered = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
            if bullet:
                prefix, line = "- ", bullet.group(1)
            elif ordered:
                prefix, line = f"{ordered.group(1)}. ", ordered.group(2)
        escaped = MARKDOWN_SPECIAL.sub(r"\\\1", html.escape(line, quote=False))
        lines.append(prefix + escaped)
    return "\n".join(lines).strip()


def next_arete_code(tags):
    numbers = [int(match.group(1)) for tag in tags if (match := TAG_PATTERN.fullmatch(tag))]
    return f"ARETE-{max(numbers, default=0) + 1:03d}"


def find_merged_pull_request(pulls):
    if isinstance(pulls, dict):
        pulls = [pulls]
    merged = [pull for pull in pulls if pull.get("state") == "closed" and pull.get("merged_at")]
    return max(merged, key=lambda pull: pull["number"], default=None)


def parse_release_summary(body):
    if body.count(RELEASE_SUMMARY_START) != 1 or body.count(RELEASE_SUMMARY_END) != 1:
        raise ValueError("Pull request body must contain one marked bilingual release summary")
    summary = body.split(RELEASE_SUMMARY_START, 1)[1].split(RELEASE_SUMMARY_END, 1)[0]
    locales = {}
    for locale, next_locale in (("English", "Türkçe"), ("Türkçe", None)):
        marker = f"## {locale}"
        if marker not in summary:
            raise ValueError(f"Release summary is missing the {locale} section")
        section = summary.split(marker, 1)[1]
        if next_locale:
            if f"## {next_locale}" not in section:
                raise ValueError(f"Release summary is missing the {next_locale} section")
            section = section.split(f"## {next_locale}", 1)[0]
        labels = {field: field for field in RELEASE_SUMMARY_FIELDS}
        if locale == "Türkçe":
            labels = {label: field for field, label in TURKISH_RELEASE_FIELDS.items()}
        fields = {}
        heading_pattern = r"^### (" + "|".join(map(re.escape, labels)) + r")\s*$"
        matches = list(re.finditer(heading_pattern, section, re.MULTILINE))
        for index, match in enumerate(matches):
            name = match.group(1)
            value = section[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(section)]
            value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL).strip()
            if name in labels:
                fields[labels[name]] = value
        missing = [name for name in RELEASE_SUMMARY_FIELDS if not fields.get(name)]
        if missing:
            raise ValueError(f"{locale} release summary has empty or missing fields: {', '.join(missing)}")
        locales[locale] = fields
    return locales


def render_notes(code, pull_request):
    number = pull_request["number"]
    title = pull_request["title"]
    url = pull_request["html_url"]
    summary = parse_release_summary(pull_request.get("body", ""))
    title = safe_release_text(re.sub(r"\s+", " ", title))
    notes = []
    for locale in ("English", "Türkçe"):
        notes.extend((f"## {locale}", "", f"`{code}` — [PR #{number}]({url}): {title}", ""))
        for field in RELEASE_SUMMARY_FIELDS:
            label = TURKISH_RELEASE_FIELDS[field] if locale == "Türkçe" else field
            notes.extend((f"### {label}", "", safe_release_text(summary[locale][field], allow_lists=True), ""))
    return "\n".join(notes).rstrip() + "\n"


def append_release_content(content, code, notes):
    heading = f"## {code}"
    if heading in content:
        return content
    return f"{content.rstrip()}\n\n{heading}\n\n{notes.strip()}\n"


def existing_release_for_pull_request(releases, pull_url):
    return next((release for release in releases if pull_url in release.get("body", "")), None)


def missing_release_assets(release, artifact_paths):
    available = {path.suffix.lower(): path for path in artifact_paths}
    missing = REQUIRED_ASSET_SUFFIXES - {
        Path(asset["name"]).suffix.lower() for asset in release.get("assets", [])
    }
    unavailable = missing - available.keys()
    if unavailable:
        raise RuntimeError(f"Missing package artifacts for release: {', '.join(sorted(unavailable))}")
    return [available[suffix] for suffix in sorted(missing)]


def validate_artifacts(artifact_paths):
    missing = REQUIRED_ASSET_SUFFIXES - {path.suffix.lower() for path in artifact_paths}
    if missing:
        raise RuntimeError(f"Missing release package artifacts: {', '.join(sorted(missing))}")


def fetch_release(code):
    return json.loads(subprocess.check_output([
        "gh", "api", f"repos/{os.environ['GITHUB_REPOSITORY']}/releases/tags/{code}",
    ], text=True))


def ensure_release_assets(code, release, artifacts):
    missing = missing_release_assets(release, artifacts)
    if missing:
        subprocess.run(["gh", "release", "upload", code, *map(str, missing)], check=True)
        release = fetch_release(code)
        missing = missing_release_assets(release, artifacts)
        if missing:
            raise RuntimeError(f"Release {code} is still missing required assets after upload")
    return release


def discover(pulls_path, github_output):
    pull = find_merged_pull_request(json.loads(pulls_path.read_text()))
    with github_output.open("a") as output:
        if pull is None:
            output.write("release=false\n")
        else:
            output.write(f"release=true\npr_number={pull['number']}\n")


def github_request(method, url, token, data=None):
    body = None if data is None else json.dumps(data).encode()
    request = urllib.request.Request(url, data=body, method=method, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "hamartia-release-workflow",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def append_release_to_github(tag, notes, repository, token):
    url = f"https://api.github.com/repos/{repository}/contents/RELEASES.md"
    for attempt in range(8):
        current = github_request("GET", f"{url}?ref=master", token)
        content = base64.b64decode(current["content"]).decode("utf-8")
        updated = append_release_content(content, tag, notes)
        if updated == content:
            return
        payload = {
            "message": f"docs: add {tag} bilingual release notes",
            "content": base64.b64encode(updated.encode()).decode(),
            "sha": current["sha"],
            "branch": "master",
        }
        try:
            github_request("PUT", url, token, payload)
            return
        except urllib.error.HTTPError as error:
            if error.code != 409 or attempt == 7:
                raise
            time.sleep(0.25 * (attempt + 1))
    raise RuntimeError("Could not update RELEASES.md after concurrent updates")


def publish_release(pulls_path, artifact_dir, target_sha, notes_path, github_output):
    pull = find_merged_pull_request(json.loads(pulls_path.read_text()))
    if pull is None:
        raise SystemExit("No merged pull request found for this commit")
    artifacts = sorted(path for path in artifact_dir.iterdir() if path.is_file())
    validate_artifacts(artifacts)

    pages = json.loads(subprocess.check_output([
        "gh", "api", "--paginate", "--slurp",
        f"repos/{os.environ['GITHUB_REPOSITORY']}/releases?per_page=100",
    ], text=True))
    existing = [release for page in pages for release in page]
    release = existing_release_for_pull_request(existing, pull["html_url"])
    if release is not None:
        code = release["tag_name"]
        notes_path.write_text(release["body"], encoding="utf-8")
    else:
        release = None
        for _ in range(20):
            subprocess.run(["git", "fetch", "--tags", "origin"], check=True)
            tags = subprocess.check_output(["git", "tag", "--list", "ARETE-*"], text=True).splitlines()
            code = next_arete_code(tags)
            notes_path.write_text(render_notes(code, pull), encoding="utf-8")
            command = [
                "gh", "release", "create", code, *map(str, artifacts),
                "--title", code, "--notes-file", str(notes_path), "--target", target_sha,
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0:
                break

            try:
                body = subprocess.check_output(
                    ["gh", "release", "view", code, "--json", "body", "--jq", ".body"], text=True,
                )
            except subprocess.CalledProcessError:
                remote_tag = subprocess.run(
                    ["git", "ls-remote", "--tags", "origin", f"refs/tags/{code}"],
                    capture_output=True, text=True,
                ).stdout
                if remote_tag:
                    continue
                raise RuntimeError(result.stderr or result.stdout or f"Could not create {code}")
            if pull["html_url"] in body:
                notes_path.write_text(body, encoding="utf-8")
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("Could not allocate an ARETE release code after 20 retries")

    if release is None or "tag_name" not in release:
        release = fetch_release(code)
    release = ensure_release_assets(code, release, artifacts)
    notes_path.write_text(release["body"], encoding="utf-8")

    with github_output.open("a") as output:
        output.write(f"tag={code}\npr_number={pull['number']}\n")


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("pulls_json", type=Path)
    discover_parser.add_argument("github_output", type=Path)
    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("pulls_json", type=Path)
    publish_parser.add_argument("artifact_dir", type=Path)
    publish_parser.add_argument("target_sha")
    publish_parser.add_argument("notes_file", type=Path)
    publish_parser.add_argument("github_output", type=Path)
    append_parser = subparsers.add_parser("append")
    append_parser.add_argument("tag")
    append_parser.add_argument("notes_file", type=Path)
    append_parser.add_argument("repository")
    append_parser.add_argument("token")
    args = parser.parse_args()

    if args.command == "discover":
        discover(args.pulls_json, args.github_output)
    elif args.command == "publish":
        publish_release(args.pulls_json, args.artifact_dir, args.target_sha, args.notes_file, args.github_output)
    else:
        append_release_to_github(args.tag, args.notes_file.read_text(encoding="utf-8"), args.repository, args.token)


if __name__ == "__main__":
    main()
