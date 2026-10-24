"""Turn an article issue (form submission) into site content. Run by .github/workflows/site.yml.

Reads the issue from $GITHUB_EVENT_PATH, checks the author has write access, updates
content/articles.json + storage/, rebuilds the HTML, and prints a summary for the issue comment.
Issue text is untrusted input: it is only ever read as data here (never put in a shell command).
"""
import datetime, hashlib, json, os, re, sys, urllib.request, urllib.parse
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github" / "builder"))
import build  # noqa: E402

ALLOWED_HOSTS = ("github.com", "user-images.githubusercontent.com", "private-user-images.githubusercontent.com",
                 "objects.githubusercontent.com", "raw.githubusercontent.com")
MAX_BYTES = 12 * 1024 * 1024
EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}
MAGIC = ((b"\x89PNG", ".png"), (b"\xff\xd8\xff", ".jpg"), (b"GIF8", ".gif"), (b"RIFF", ".webp"))


class Reject(Exception):
    """A problem the editor should be told about (posted as an issue comment)."""


def api(path):
    req = urllib.request.Request("https://api.github.com" + path, headers={
        "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"], "Accept": "application/vnd.github+json",
        "User-Agent": "ieeeias-article-bot"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def has_write_access(user):
    try:
        perm = api(f'/repos/{os.environ["GITHUB_REPOSITORY"]}/collaborators/{urllib.parse.quote(user)}/permission')
        return perm.get("permission") in ("admin", "maintain", "write")
    except Exception:
        return False


def parse_form(body):
    """GitHub issue-form body -> {label: value}. Empty answers become ''."""
    out, key, buf = {}, None, []
    for line in body.replace("\r\n", "\n").split("\n"):
        if line.startswith("### "):
            if key is not None:
                out[key] = "\n".join(buf).strip()
            key, buf = line[4:].strip(), []
        else:
            buf.append(line)
    if key is not None:
        out[key] = "\n".join(buf).strip()
    return {k: ("" if v == "_No response_" else v) for k, v in out.items()}


def field(form, prefix):
    for k, v in form.items():
        if k.lower().startswith(prefix.lower()):
            return v
    return ""


def fetch(url):
    """Download an image attached to the issue. Only GitHub hosts, images only, size-limited."""
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or not (u.hostname in ALLOWED_HOSTS or u.hostname.endswith(".githubusercontent.com")):
        raise Reject(f"Image address not allowed (only images uploaded to GitHub): {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "ieeeias-article-bot", "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"]}
                                 if u.hostname == "github.com" else {"User-Agent": "ieeeias-article-bot"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(MAX_BYTES + 1)
        ctype = r.headers.get_content_type()
    if len(data) > MAX_BYTES:
        raise Reject("An image is larger than 12 MB - please shrink it.")
    ext = EXT.get(ctype) or next((e for m, e in MAGIC if data.startswith(m)), None)
    if not ext:
        raise Reject(f"Not a supported image (png, jpg, gif, webp): {url}")
    return data, ext


def save_image(url, sub):
    data, ext = fetch(url)
    d = ROOT / "storage" / "articles" / sub if sub else ROOT / "storage" / "articles"
    d.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(data).hexdigest()[:20] + ext
    (d / name).write_bytes(data)
    return "/storage/articles/" + (sub + "/" if sub else "") + name


IMG_MD = re.compile(r'!\[([^\]]*)\]\((https?://[^)\s]+)[^)]*\)')
IMG_HTML = re.compile(r'<img\b[^>]*?\bsrc="(https?://[^"]+)"[^>]*>', re.I)


def localise_images(text):
    """Replace remote image links in the text with files saved under /storage."""
    def md(m):
        return f'![{m.group(1)}]({save_image(m.group(2), "body")})'
    def html(m):
        alt = re.search(r'alt="([^"]*)"', m.group(0))
        return f'![{alt.group(1) if alt else ""}]({save_image(m.group(1), "body")})'
    text = IMG_HTML.sub(html, text)
    return IMG_MD.sub(md, text)


def to_html(text):
    return markdown.markdown(text, extensions=["extra", "sane_lists"])


def first_image_url(text):
    m = IMG_MD.search(text) or IMG_HTML.search(text)
    return (m.group(2) if m and m.re is IMG_MD else m.group(1)) if m else ""


def process(event):
    issue = event["issue"]
    user = issue["user"]["login"]
    if not has_write_access(user):
        raise Reject(f"@{user} does not have write access to this repository, so this was not published.")
    labels = {l["name"] for l in issue.get("labels", [])}
    form = parse_form(issue.get("body") or "")
    data = build.load(ROOT)
    arts = data["articles"]

    if "article-delete" in labels:
        slug = field(form, "Article address").strip().strip("/").split("/")[-1]
        art = next((a for a in arts if a["slug"] == slug), None)
        if not art:
            raise Reject(f"No article with the address `{slug}`.")
        arts.remove(art)
        build.save(ROOT, data); build.build(ROOT)
        return f'Deleted "{art["title"]}".'

    title = field(form, "Title")
    cats = {name.lower(): key for key, name in data["categories"]}
    category = cats.get(field(form, "Category").lower())
    slug = field(form, "Existing article address").strip().strip("/").split("/")[-1]
    art = next((a for a in arts if a["slug"] == slug), None) if slug else None
    if slug and not art:
        raise Reject(f"No article with the address `{slug}` to update.")
    if not art and (not title or not category or not field(form, "Article text")):
        raise Reject("A new article needs a title, a category and the article text.")

    new = art is None
    if new:
        base, n = build.slugify(title), 2
        slug = base
        while any(a["slug"] == slug for a in arts):
            slug, n = f"{base}-{n}", n + 1
        art = dict(slug=slug, title="", category="", date=datetime.date.today().isoformat(), author="Administrator",
                   image="", card_image="", summary="", featured=False, body="")
        arts.insert(0, art)

    if title: art["title"] = title
    if category: art["category"] = category
    d = field(form, "Date")
    if d:
        try:
            art["date"] = datetime.date.fromisoformat(d).isoformat()
        except ValueError:
            raise Reject(f"Date `{d}` must look like 2026-10-31.")
    if field(form, "Author"): art["author"] = field(form, "Author")
    cover = field(form, "Cover image")
    if cover:
        url = first_image_url(cover)
        if not url:
            raise Reject("The cover image field has no picture - drag and drop an image into it.")
        art["image"] = save_image(url, "")
    text = field(form, "Article text")
    if text:
        art["body"] = to_html(localise_images(text))
    if field(form, "Summary"): art["summary"] = field(form, "Summary")
    if re.search(r"\[x\]", field(form, "Options"), re.I):
        for a in arts:
            a["featured"] = False
        art["featured"] = True

    build.save(ROOT, data); build.build(ROOT)
    return f'{"Published" if new else "Updated"} "{art["title"]}": https://ieeeias.my.id/articles/{art["slug"]}'


def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    out = Path(os.environ.get("RESULT_FILE", "result.json"))
    try:
        msg = process(event); ok = True
    except Reject as e:
        msg, ok = str(e), False
    except Exception as e:  # unexpected: report it, do not publish anything
        msg, ok = f"Unexpected error: {type(e).__name__}: {e}", False
    out.write_text(json.dumps({"ok": ok, "message": msg}))
    print(msg)
    sys.exit(0)


if __name__ == "__main__":
    main()
