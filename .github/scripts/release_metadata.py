"""Generate sequential ARETE codes and bilingual GitHub release notes."""

import argparse
import base64
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


TAG_PATTERN = re.compile(r"^ARETE-(\d+)$")


def next_arete_code(tags):
    numbers = [int(match.group(1)) for tag in tags if (match := TAG_PATTERN.fullmatch(tag))]
    return f"ARETE-{max(numbers, default=0) + 1:03d}"


def find_merged_pull_request(pulls):
    if isinstance(pulls, dict):
        pulls = [pulls]
    merged = [pull for pull in pulls if pull.get("state") == "closed" and pull.get("merged_at")]
    return max(merged, key=lambda pull: pull["number"], default=None)


def render_notes(code, pull_request):
    number = pull_request["number"]
    title = pull_request["title"]
    url = pull_request["html_url"]
    return f"""## English

`{code}` includes the changes merged in [PR #{number}: {title}]({url}).

This release contains the Windows installer, Debian package, and AppImage built from that merge. Study data stays in the current user's application data directory.

## Türkçe

`{code}` sürümü, [#{number} numaralı PR'da birleştirilen Hamartia güncellemesini]({url}) içerir.

Bu sürüm Windows kurulum programını, Debian paketini ve AppImage dosyasını içerir. Çalışma verileri mevcut kullanıcının uygulama verileri klasöründe saklanır.
"""


def append_release_content(content, code, notes):
    heading = f"## {code}"
    if heading in content:
        return content
    return f"{content.rstrip()}\n\n{heading}\n\n{notes.strip()}\n"


def existing_release_for_pull_request(releases, pull_url):
    return next((release for release in releases if pull_url in release.get("body", "")), None)


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
        return json.loads(response.read())


def append_release_to_github(tag, notes, repository, token):
    url = f"https://api.github.com/repos/{repository}/contents/RELEASES.md"
    for attempt in range(8):
        current = github_request("GET", f"{url}?ref=master", token)
        content = base64.b64decode(current["content"]).decode()
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
    if not artifacts:
        raise SystemExit(f"No release artifacts found in {artifact_dir}")

    pages = json.loads(subprocess.check_output([
        "gh", "api", "--paginate", "--slurp",
        f"repos/{os.environ['GITHUB_REPOSITORY']}/releases?per_page=100",
    ], text=True))
    existing = [release for page in pages for release in page]
    release = existing_release_for_pull_request(existing, pull["html_url"])
    if release is not None:
        code = release["tag_name"]
        notes_path.write_text(release["body"])
    else:
        for _ in range(20):
            subprocess.run(["git", "fetch", "--tags", "origin"], check=True)
            tags = subprocess.check_output(["git", "tag", "--list", "ARETE-*"], text=True).splitlines()
            code = next_arete_code(tags)
            notes_path.write_text(render_notes(code, pull))
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
                notes_path.write_text(body)
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("Could not allocate an ARETE release code after 20 retries")

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
        append_release_to_github(args.tag, args.notes_file.read_text(), args.repository, args.token)


if __name__ == "__main__":
    main()
