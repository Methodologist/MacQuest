"""
Upload a packaged release to CurseForge (used by .github/workflows/release.yml).

    CF_API_TOKEN=...  CF_PROJECT_ID=...  python tools/curseforge_upload.py dist/MacQuest-0.7.0.zip
    CF_API_TOKEN=...  python tools/curseforge_upload.py --list-versions     # find the game version id

Environment:
    CF_API_TOKEN      CurseForge API token (authors console -> API tokens); a GitHub secret in CI
    CF_PROJECT_ID     the project's numeric id (shown on the project page)
    CF_GAME_VERSION   game version name(s) as CurseForge lists them, comma separated (e.g. "1.15.7");
                      default: matched from the .toc Interface number
    CF_RELEASE_TYPE   release | beta | alpha (default: beta while the route is not fully playtested)

The changelog is the section of CHANGELOG.md for this version.
"""
import json
import os
import re
import sys
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://wow.curseforge.com/api"


def request(url, token, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"X-Api-Token": token, "User-Agent": "MacQuest-release",
                                                          **(headers or {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def game_versions(token):
    return request(f"{API}/game/versions", token)


def interface_to_version(interface):
    """16001 -> "1.60.1", 11507 -> "1.15.7" (the usual TOC Interface encoding)"""
    s = str(interface)
    major = int(s[:-4]) if len(s) > 4 else 0
    minor, patch = int(s[-4:-2]), int(s[-2:])
    return f"{major}.{minor}.{patch}"


def pick_versions(token):
    names = [n.strip() for n in os.environ.get("CF_GAME_VERSION", "").split(",") if n.strip()]
    if not names:
        toc = (ROOT / "SpeedLevel" / "SpeedLevel.toc").read_text(encoding="utf-8")
        names = [interface_to_version(re.search(r"## Interface:\s*(\d+)", toc).group(1))]
    allv = game_versions(token)
    ids = [v["id"] for v in allv if v.get("name") in names]
    if not ids:
        close = sorted({v["name"] for v in allv if v.get("name", "").split(".")[0] == names[0].split(".")[0]})
        raise SystemExit(f"CurseForge has no game version named {names}. Set CF_GAME_VERSION to one of: "
                         f"{', '.join(close[-25:])}")
    return ids


def changelog(version):
    p = ROOT / "CHANGELOG.md"
    if not p.exists():
        return f"Mac Quest {version}"
    text = p.read_text(encoding="utf-8")
    m = re.search(rf"^## {re.escape(version)}\b.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return (m.group(1).strip() if m else f"Mac Quest {version}")


def upload(zip_path, token, project):
    zip_path = Path(zip_path)
    version = re.search(r"-(\d[\w.\-]*)\.zip$", zip_path.name).group(1)
    meta = {
        "changelog": changelog(version),
        "changelogType": "markdown",
        "displayName": f"Mac Quest {version}",
        "gameVersions": pick_versions(token),
        "releaseType": os.environ.get("CF_RELEASE_TYPE", "beta"),
    }
    boundary = uuid.uuid4().hex
    body = b"".join([
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"metadata\"\r\n"
        f"Content-Type: application/json\r\n\r\n".encode(), json.dumps(meta).encode(), b"\r\n",
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{zip_path.name}\"\r\n"
        f"Content-Type: application/zip\r\n\r\n".encode(), zip_path.read_bytes(), b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    res = request(f"{API}/projects/{project}/upload-file", token, data=body,
                  headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    print(f"uploaded {zip_path.name} to CurseForge project {project}: file id {res.get('id')}")


def main():
    token = os.environ.get("CF_API_TOKEN")
    if not token:
        raise SystemExit("CF_API_TOKEN is not set")
    if "--list-versions" in sys.argv:
        for v in game_versions(token):
            print(v["id"], v["name"])
        return
    project = os.environ.get("CF_PROJECT_ID")
    if not project or len(sys.argv) < 2:
        raise SystemExit(__doc__)
    upload(sys.argv[1], token, project)


if __name__ == "__main__":
    main()
