"""Static site generator for ieeeias.my.id.

Reads <site>/content/articles.json + ./templates and writes the HTML pages
into the site folder (the git repository GitHub Pages publishes).
"""
import json, re, shutil, datetime
from html import escape
from pathlib import Path

APP = Path(__file__).resolve().parent
SITE = "IEEE IAS Indonesia Chapter"
HOME_COUNT = 4


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:120].strip("-") or "article"


def load(root):
    return json.loads((Path(root) / "content" / "articles.json").read_text(encoding="utf-8"))


def save(root, data):
    (Path(root) / "content" / "articles.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def fmt_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B')}, {d.year}"


def page(head, foot, title, bodyclass, nav, content):
    h = head.replace("{{TITLE}}", escape(title)).replace("{{BODYCLASS}}", bodyclass).replace("{{NAV}}", nav)
    return h + '<div id="content" class="site-content">\n' + content + "\n    </div>\n\n" + foot


def build(root, data=None, out=None):
    """Write the site. `data` overrides articles.json and `out` redirects the HTML output (used for previews)."""
    ROOT = Path(out or root)
    data = data or load(root)
    cats = dict(data["categories"])
    arts = sorted(data["articles"], key=lambda a: a["date"], reverse=True)  # stable: file order breaks ties
    head = (APP / "templates" / "head.html").read_text(encoding="utf-8")
    foot = (APP / "templates" / "foot.html").read_text(encoding="utf-8")

    def nav(active):
        items = [("home", "/", "Home"), ("articles", "/articles", "Articles")]
        items += [("cat-" + k, f"/articles?category={k}", v) for k, v in data["categories"]]
        return "\n".join(
            f'<li class="{"current-menu-item" if k == active else ""}"><a href="{u}">{n}</a></li>' for k, u, n in items)

    def card(a):
        c = a["category"]
        pic = a.get("card_image") or a.get("image")
        img = (f'<div class="featured-image "  style="background-image: url(\'{pic}\');" >'
               if pic else '<div class="featured-image no-image" >')
        return f'''<li class="col-lg-4 col-md-4 col-sm-6 col-xs-12" data-category="{c}" data-title="{escape(a["title"].lower())}">
    {img}
        <div class="title">
            <ul class="tags"><li><a href="/articles?category={c}">{escape(cats.get(c, c))}</a></li></ul>
            <h4><a href="/articles/{a["slug"]}">{escape(a["title"])}</a></h4>
        </div>
    </div>
</li>'''

    # wipe generated article pages (keep everything else)
    adir = ROOT / "articles"
    if adir.exists():
        shutil.rmtree(adir)
    adir.mkdir()

    # article pages
    for a in arts:
        img = (f'<img class="img-responsive article-image" src="{a["image"]}" alt="{escape(a["title"])}">'
               if a.get("image") else "")
        c = a["category"]
        content = f'''<div class="container">
        <div class="row">
            <div class="col-lg-12">
                <article class="post" itemscope itemtype="https://schema.org/BlogPosting">
                    <div class="entry-content">
                        <header class="article-header">
                            <h1 class="page-title" itemprop="headline">{escape(a["title"])}</h1>
                            <div class="author">By {escape(a.get("author") or "Administrator")} · <a href="/articles?category={c}">{escape(cats.get(c, c))}</a></div>
                            <div class="date">{fmt_date(a["date"])}</div>
                        </header>
                        {img}
                        <section class="post-content clearfix" style="margin-top: 20px;">
                            {a["body"]}
                        </section>
                        <p><a href="/articles">&larr; All articles</a></p>
                    </div>
                </article>
            </div>
        </div>
    </div>'''
        out = adir / a["slug"]
        out.mkdir()
        (out / "index.html").write_text(
            page(head, foot, f'{a["title"]} – {SITE}', "single", nav("articles"), content), encoding="utf-8")

    # articles list (filtering by ?category= and ?q= happens client side so URLs match the old site)
    cards = "\n".join(card(a) for a in arts)
    lst = f'''<div class="container">
        <header class="article-header">
            <h1 class="page-title" id="list-title">Articles</h1>
        </header>
        <div class="posts">
            <ul class="tiled row tiled-3" id="article-list">
{cards}
            </ul>
            <p id="no-results" style="display:none">No articles found.</p>
        </div>
    </div>
    <script>
    (function () {{
        var p = new URLSearchParams(location.search), cat = p.get("category"), q = (p.get("q") || "").toLowerCase().trim();
        var names = {json.dumps(cats)}, shown = 0;
        document.querySelectorAll("#article-list > li").forEach(function (li) {{
            var ok = (!cat || li.dataset.category === cat) && (!q || li.dataset.title.indexOf(q) !== -1);
            li.style.display = ok ? "" : "none"; if (ok) shown++;
        }});
        if (!shown) document.getElementById("no-results").style.display = "";
        var t = document.getElementById("list-title");
        if (cat && names[cat]) t.textContent = names[cat];
        if (q) t.textContent = 'Search: "' + p.get("q") + '"';
        document.querySelectorAll("#nav li").forEach(function (li) {{
            var a = li.querySelector("a"), href = a.getAttribute("href");
            li.className = (href === "/articles" + (cat ? "?category=" + cat : "")) ? "current-menu-item" : "";
        }});
        var s = document.getElementById("search-form"); if (s && q) s.value = p.get("q");
    }})();
    </script>'''
    (adir / "index.html").write_text(page(head, foot, f"Articles – {SITE}", "", nav("articles"), lst), encoding="utf-8")

    # home
    feat = next((a for a in arts if a.get("featured")), None)
    if feat:
        style = ""
        slide = f'''<div class="container-fluid full-width">
            <div class="slideshow-container">
                <div class="slideshow">
                    <div class="slide white no-image"{style}>
                        <div class="container">
                            <div class="row">
                                <div class="col-lg-6 col-md-6 col-sm-12 content overlay">
                                    <div class="inner-content">
                                        <h1>{escape(feat["title"])}</h1>
                                        {"<h2>" + escape(feat["summary"]) + "</h2>" if feat.get("summary") else ""}
                                        <a class="btn btn-primary" href="/articles/{feat["slug"]}">Read more</a>
                                    </div>
                                </div>
                                <div class="col-lg-6 col-md-6 col-sm-12"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>'''
    else:
        slide = ""
    latest = "\n".join(card(a) for a in [a for a in arts if a is not feat][:HOME_COUNT])
    home = f'''{slide}
    <div class="container home-articles">
        <div class="posts">
            <h3 class="boxed tiled"><span>Latest Articles</span></h3>
            <ul class="tiled row tiled-3">
{latest}
            </ul>
        </div>
        <a href="/articles" class="btn btn-primary btn-block more">See All Articles</a>
    </div>'''
    (ROOT / "index.html").write_text(page(head, foot, SITE, "home", nav("home"), home), encoding="utf-8")

    # 404 + Pages housekeeping
    nf = '<div class="container"><header class="article-header"><h1 class="page-title">Page not found</h1></header><p><a href="/">&larr; Back to home</a></p></div>'
    (ROOT / "404.html").write_text(page(head, foot, f"Not Found – {SITE}", "", nav(""), nf), encoding="utf-8")
    (ROOT / "CNAME").write_text("ieeeias.my.id\n")
    (ROOT / ".nojekyll").write_text("")
    return len(arts)


if __name__ == "__main__":
    import sys
    print(f"Built {build(sys.argv[1])} articles")
