import json
import os
import re
import time
from datetime import datetime, timezone
from urllib import request
from xml.etree import ElementTree

# ── CONFIG — reads from environment variables (GitHub Secrets) ────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN      = os.environ.get("GH_TOKEN", "")
GITHUB_REPO       = "Explore2035/explore2035"
ARTICLES_FILE     = "articles.json"
MAX_ARTICLES_PER_CAT = 5
MAX_ARCHIVE       = 500

# ── RSS FEEDS PER CATEGORY ────────────────────────────────────────────────────
FEEDS = {
    "ai":        ["https://techcrunch.com/feed/", "https://venturebeat.com/feed/"],
    "robotics":  ["https://techcrunch.com/feed/", "https://www.sciencedaily.com/rss/computers_math/robotics.xml"],
    "biotech":   ["https://www.sciencedaily.com/rss/health_medicine/biotechnology.xml", "https://www.sciencedaily.com/rss/health_medicine.xml"],
    "space":     ["https://www.sciencedaily.com/rss/space_time.xml", "https://spacenews.com/feed/"],
    "gadgets":   ["https://www.theverge.com/rss/index.xml", "https://feeds.feedburner.com/TechRadar-All-Articles"],
    "ev":        ["https://electrek.co/feed/", "https://insideevs.com/feed/"],
    "fintech":   ["https://techcrunch.com/feed/", "https://www.coindesk.com/arc/outboundfeeds/rss/"],
    "climate":   ["https://www.sciencedaily.com/rss/earth_climate.xml", "https://cleantechnica.com/feed/"],
    "gaming":    ["https://www.theverge.com/rss/index.xml", "https://venturebeat.com/feed/"],
    "cyber":     ["https://www.wired.com/feed/category/security/latest/rss", "https://techcrunch.com/feed/"],
    "smarthome": ["https://www.theverge.com/rss/index.xml", "https://www.cnet.com/rss/news/"],
    "drones":    ["https://techcrunch.com/feed/", "https://www.theverge.com/rss/index.xml"],
    "longevity": ["https://www.sciencedaily.com/rss/health_medicine.xml", "https://venturebeat.com/feed/"],
    "hair":      ["https://www.sciencedaily.com/rss/health_medicine.xml", "https://www.medicalnewstoday.com/rss"],
}

KEYWORDS = {
    "ai":        ["artificial intelligence","machine learning","gpt","openai","deepmind","llm","neural network","chatbot","claude","gemini","copilot","large language"],
    "robotics":  ["robot","robotic","humanoid","boston dynamics","unitree","figure ai","mechanical arm","autonomous machine"],
    "biotech":   ["biotech","crispr","gene editing","gene therapy","genomics","clinical trial","drug discovery","mrna","stem cell","biopharma"],
    "space":     ["nasa","spacex","rocket launch","satellite","mars","lunar","orbit","space station","astronaut","telescope","fusion energy"],
    "gadgets":   ["iphone","samsung galaxy","apple watch","headset","wearable","smartphone","laptop","tablet","vr headset","ar glasses","consumer tech"],
    "ev":        ["electric vehicle","tesla","rivian","lucid","waymo","self-driving","autonomous vehicle","charging station","battery range"],
    "fintech":   ["bitcoin","cryptocurrency","blockchain","fintech","defi","digital payment","stripe","coinbase","stablecoin"],
    "climate":   ["climate","renewable energy","solar panel","wind energy","carbon capture","green hydrogen","net zero","clean energy","emissions"],
    "gaming":    ["video game","gaming","nvidia","playstation","xbox","metaverse","virtual reality","game engine","esports"],
    "cyber":     ["cybersecurity","hack","data breach","ransomware","malware","phishing","zero day","encryption","cyber attack"],
    "smarthome": ["smart home","alexa","google home","matter protocol","iot","connected device","smart speaker","home automation"],
    "drones":    ["drone","uav","evtol","air taxi","unmanned","aerial vehicle","joby","drone delivery","faa"],
    "longevity": ["longevity","anti-aging","lifespan","senolytic","rapamycin","cellular aging","healthspan","biological age","rejuvenation"],
    "hair":      ["hair loss","hair regrowth","alopecia","hair follicle","baldness","minoxidil","finasteride","hair transplant","jak inhibitor"],
}

def fetch_url(url, timeout=15):
    try:
        req = request.Request(url, headers={"User-Agent": "Mozilla/5.0 Explore2035Bot/1.0"})
        with request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  fetch error {url}: {e}")
        return None

def strip_html(text):
    return re.sub(r"<[^>]+>", " ", text).strip()

def parse_rss(xml_text):
    items = []
    try:
        root = ElementTree.fromstring(xml_text)
        for item in root.iter("item"):
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            desc  = item.findtext("description", "").strip()
            pub   = item.findtext("pubDate", "").strip()
            if title and link:
                items.append({"title": title, "url": link, "desc": strip_html(desc)[:300], "pub": pub})
        if not items:
            for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                title = entry.findtext("{http://www.w3.org/2005/Atom}title", "").strip()
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
                link  = link_el.get("href", "") if link_el is not None else ""
                desc  = entry.findtext("{http://www.w3.org/2005/Atom}summary", "").strip()
                pub   = entry.findtext("{http://www.w3.org/2005/Atom}updated", "").strip()
                if title and link:
                    items.append({"title": title, "url": link, "desc": strip_html(desc)[:300], "pub": pub})
    except Exception as e:
        print(f"  parse error: {e}")
    return items

def matches_cat(item, cat):
    text = (item["title"] + " " + item["desc"]).lower()
    return any(kw in text for kw in KEYWORDS[cat])

def summarize(title, desc):
    prompt = (
        f"You are a tech journalist for Explore2035.com. "
        f"Write a 2-3 sentence summary in plain English for a curious general audience. "
        f"Be specific, factual, and engaging. No hype.\n\n"
        f"Title: {title}\nDescription: {desc}\n\nSummary:"
    )
    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 200,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"  summarize error: {e}")
        return desc[:200]

def time_ago(pub_str):
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(pub_str)
        diff = (datetime.now(timezone.utc) - dt).total_seconds()
        if diff < 3600:  return f"{int(diff//60)}m ago"
        if diff < 86400: return f"{int(diff//3600)}h ago"
        return f"{int(diff//86400)}d ago"
    except:
        return "recently"

def github_get(path):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    req = request.Request(url, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Explore2035Bot",
    })
    try:
        with request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except:
        return None

def github_put(path, content_str, message, sha=None):
    import base64
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    payload = {"message": message, "content": base64.b64encode(content_str.encode()).decode()}
    if sha:
        payload["sha"] = sha
    data = json.dumps(payload).encode()
    req = request.Request(url, data=data, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "Explore2035Bot",
    }, method="PUT")
    try:
        with request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  github put error: {e}")
        return None

def run():
    print(f"\n{'='*60}")
    print(f"Explore2035 Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    existing = github_get(ARTICLES_FILE)
    if existing:
        import base64
        old_data = json.loads(base64.b64decode(existing["content"]).decode())
        sha = existing["sha"]
    else:
        old_data = {"today": [], "archive": []}
        sha = None

    archive = old_data.get("today", []) + old_data.get("archive", [])
    archive = archive[:MAX_ARCHIVE]

    today = []
    seen_titles = set()

    for cat, feed_urls in FEEDS.items():
        print(f"\n📂 {cat.upper()}")
        cat_articles = []
        for feed_url in feed_urls:
            if len(cat_articles) >= MAX_ARTICLES_PER_CAT:
                break
            print(f"  Fetching {feed_url}")
            xml = fetch_url(feed_url)
            if not xml:
                continue
            items = parse_rss(xml)
            for item in items:
                if len(cat_articles) >= MAX_ARTICLES_PER_CAT:
                    break
                if item["title"] in seen_titles:
                    continue
                if not matches_cat(item, cat):
                    continue
                print(f"  ✓ {item['title'][:60]}")
                summary = summarize(item["title"], item["desc"])
                cat_articles.append({
                    "cat":   cat,
                    "title": item["title"],
                    "sum":   summary,
                    "src":   feed_url.split("/")[2].replace("www.", ""),
                    "age":   time_ago(item["pub"]),
                    "url":   item["url"],
                    "date":  datetime.now().strftime("%B %d, %Y"),
                })
                seen_titles.add(item["title"])
                time.sleep(0.5)
        today.extend(cat_articles)
        print(f"  → {len(cat_articles)} articles for {cat}")

    print(f"\n✅ Total today: {len(today)} articles")
    print(f"✅ Archive: {len(archive)} articles")

    new_data = {
        "today": today,
        "archive": archive,
        "updated": datetime.now().isoformat()
    }
    result = github_put(
        ARTICLES_FILE,
        json.dumps(new_data, indent=2),
        f"Auto-update {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        sha,
    )
    if result:
        print("✅ articles.json saved to GitHub!")
    else:
        print("❌ Failed to save to GitHub")

if __name__ == "__main__":
    run()
