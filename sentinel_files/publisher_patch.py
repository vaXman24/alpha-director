"""
PATCH — add this block to publisher.py on the VPS after the existing publish() function.
"""

_TRENDS_PATH = "docs/trends.json"
_TRENDS_API  = f"https://api.github.com/repos/{_REPO}/contents/{_TRENDS_PATH}"


def publish_trends(trends_data: dict) -> bool:
    """Upload trends.json to GitHub Pages (docs/trends.json)."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        log.debug("GITHUB_TOKEN not set — trends publish skipped")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    sha: str | None = None
    try:
        r = requests.get(_TRENDS_API, headers=headers, timeout=10)
        if r.ok:
            sha = r.json().get("sha")
    except Exception as e:
        log.warning("publisher: could not fetch trends SHA: %s", e)

    content_bytes = json.dumps(trends_data, indent=2, default=str).encode("utf-8")
    payload: dict = {
        "message": f"auto: trends {trends_data.get('updated', 'update')}",
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "branch":  _BRANCH,
    }
    if sha:
        payload["sha"] = sha

    try:
        r = requests.put(_TRENDS_API, headers=headers, json=payload, timeout=20)
        if r.ok:
            log.info("trends.json published → GitHub Pages")
            return True
        log.warning("publisher: trends PUT failed %s: %s", r.status_code, r.text[:200])
        return False
    except Exception as e:
        log.warning("publisher: trends request error: %s", e)
        return False
