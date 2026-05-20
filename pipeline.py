import json, os, re, time, base64
from datetime import datetime, timezone
from urllib import request
from xml.etree import ElementTree

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN      = os.environ.get("GH_TOKEN", "")
GITHUB_REPO       = "Explore2035/explore2035"
MAX_PER_CAT       = 5
MAX_ARCHIVE       = 500

FEEDS = {
    "ai":        ["https://techcrunch.com/feed/","https://venturebeat.com/feed/"],
    "robotics":  ["https://techcrunch.com/feed/","https://www.sciencedaily.com/rss/computers_math/robotics.xml"],
    "biotech":   ["https://www.sciencedaily.com/rss/health_medicine/biotechnology.xml","https://www.sciencedaily.com/rss/health_medicine.xml"],
    "space":     ["https://www.sciencedaily.com/rss/space_time.xml","https://spacenews.com/feed/"],
    "gadgets":   ["https://www.theverge.com/rss/index.xml","https://feeds.feedburner.com/TechRadar-All-Articles"],
    "ev":        ["https://electrek.co/feed/","https://insideevs.com/feed/"],
    "fintech":   ["https://techcrunch.com/feed/","https://www.coindesk.com/arc/outboundfeeds/rss/"],
    "climate":   ["https://www.sciencedaily.com/rss/earth_climate.xml","https://cleantechnica.com/feed/"],
    "gaming":    ["https://www.theverge.com/rss/index.xml","https://venturebeat.com/feed/"],
    "cyber":     ["https://www.wired.com/feed/category/security/latest/rss","https://techcrunch.com/feed/"],
    "smarthome": ["https://www.theverge.com/rss/index.xml","https://www.cnet.com/rss/news/"],
    "drones":    ["https://techcrunch.com/feed/","https://www.theverge.com/rss/index.xml"],
    "longevity": ["https://www.sciencedaily.com/rss/health_medicine.xml","https://venturebeat.com/feed/"],
    "hair":      ["https://www.sciencedaily.com/rss/health_medicine.xml","https://www.medicalnewstoday.com/rss"],
}

KEYWORDS = {
    "ai":        ["artificial intelligence","machine learning","gpt","openai","deepmind","llm","neural","chatbot","claude","gemini"],
    "robotics":  ["robot","robotic","humanoid","boston dynamics","unitree","figure ai","autonomous machine"],
    "biotech":   ["biotech","crispr","gene","genomics","clinical trial","drug discovery","mrna","stem cell","biopharma"],
    "space":     ["nasa","spacex","rocket","satellite","mars","lunar","orbit","space station","astronaut","fusion energy"],
    "gadgets":   ["iphone","samsung","apple watch","headset","wearable","smartphone","laptop","tablet","vr","ar glasses"],
    "ev":        ["electric vehicle","tesla","rivian","lucid","waymo","self-driving","charging station","battery range"],
    "fintech":   ["bitcoin","cryptocurrency","blockchain","fintech","defi","digital payment","stripe","coinbase"],
    "climate":   ["climate","renewable energy","solar","wind energy","carbon capture","green hydrogen","net zero","clean energy"],
    "gaming":    ["video game","gaming","nvidia","playstation","xbox","metaverse","virtual reality","esports"],
    "cyber":     ["cybersecurity","hack","data breach","ransomware","malware","phishing","zero day","encryption"],
    "smarthome": ["smart home","alexa","google home","matter","iot","connected device","smart speaker","home automation"],
    "drones":    ["drone","uav","evtol","air taxi","unmanned","aerial","joby","drone delivery","faa"],
    "longevity": ["longevity","anti-aging","lifespan","senolytic","rapamycin","cellular aging","healthspan","rejuvenation"],
    "hair":      ["hair loss","hair regrowth","alopecia","hair follicle","baldness","minoxidil","finasteride","jak inhibitor"],
}

def fetch_url(url):
    try:
        req = request.Request(url, headers={"User-Agent":"Mozilla/5.0 Explore2035Bot/1.0"})
        with request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  fetch error {url}: {e}"); return None

def strip_html(text):
    return re.sub(r"<[^>]+>"," ",text).strip()

def parse_rss(xml_text):
    items=[]
    try:
        root=ElementTree.fromstring(xml_text)
        for item in root.iter("item"):
            t=item.findtext("title","").strip()
            l=item.findtext("link","").strip()
            d=item.findtext("description","").strip()
            p=item.findtext("pubDate","").strip()
            if t and l: items.append({"title":t,"url":l,"desc":strip_html(d)[:300],"pub":p})
        if not items:
            for e in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                t=e.findtext("{http://www.w3.org/2005/Atom}title","").strip()
                le=e.find("{http://www.w3.org/2005/Atom}link")
                l=le.get("href","") if le is not None else ""
                d=e.findtext("{http://www.w3.org/2005/Atom}summary","").strip()
                p=e.findtext("{http://www.w3.org/2005/Atom}updated","").strip()
                if t and l: items.append({"title":t,"url":l,"desc":strip_html(d)[:300],"pub":p})
    except Exception as e:
        print(f"  parse error: {e}")
    return items

def matches(item, cat):
    text=(item["title"]+" "+item["desc"]).lower()
    return any(kw in text for kw in KEYWORDS[cat])

def summarize(title, desc):
    prompt=f"You are a tech journalist for Explore2035.com. Write a 2-3 sentence summary in plain English for a curious general audience. Be specific and factual.\n\nTitle: {title}\nDescription: {desc}\n\nSummary:"
    payload=json.dumps({"model":"claude-sonnet-4-20250514","max_tokens":200,"messages":[{"role":"user","content":prompt}]}).encode()
    req=request.Request("https://api.anthropic.com/v1/messages",data=payload,
        headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"},method="POST")
    try:
        with request.urlopen(req,timeout=30) as r:
            return json.loads(r.read())["content"][0]["text"].strip()
    except Exception as e:
        print(f"  summarize error: {e}"); return desc[:200]

def time_ago(pub):
    try:
        from email.utils import parsedate_to_datetime
        diff=(datetime.now(timezone.utc)-parsedate_to_datetime(pub)).total_seconds()
        if diff<3600: return f"{int(diff//60)}m ago"
        if diff<86400: return f"{int(diff//3600)}h ago"
        return f"{int(diff//86400)}d ago"
    except: return "recently"

def gh_get(path):
    url=f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    req=request.Request(url,headers={"Authorization":f"token {GITHUB_TOKEN}","Accept":"application/vnd.github.v3+json","User-Agent":"Explore2035Bot"})
    try:
        with request.urlopen(req,timeout=15) as r: return json.loads(r.read())
    except: return None

def gh_put(path, content, message, sha=None):
    url=f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    payload={"message":message,"content":base64.b64encode(content.encode()).decode()}
    if sha: payload["sha"]=sha
    req=request.Request(url,data=json.dumps(payload).encode(),
        headers={"Authorization":f"token {GITHUB_TOKEN}","Accept":"application/vnd.github.v3+json","Content-Type":"application/json","User-Agent":"Explore2035Bot"},method="PUT")
    try:
        with request.urlopen(req,timeout=15) as r: return json.loads(r.read())
    except Exception as e:
        print(f"  gh_put error: {e}"); return None

def run():
    print(f"\n{'='*60}\nExplore2035 Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{'='*60}")

    # Load existing data
    existing = gh_get("articles.json")
    if existing:
        old = json.loads(base64.b64decode(existing["content"]).decode())
        articles_sha = existing["sha"]
    else:
        old = {"today":[],"archive":[]}
        articles_sha = None

    # Move today to archive
    archive = old.get("today",[]) + old.get("archive",[])
    archive = archive[:MAX_ARCHIVE]

    # Fetch fresh articles
    today = []
    seen = set()

    for cat, feeds in FEEDS.items():
        print(f"\n📂 {cat.upper()}")
        cat_arts = []
        for feed in feeds:
            if len(cat_arts) >= MAX_PER_CAT: break
            xml = fetch_url(feed)
            if not xml: continue
            for item in parse_rss(xml):
                if len(cat_arts) >= MAX_PER_CAT: break
                if item["title"] in seen: continue
                if not matches(item, cat): continue
                print(f"  ✓ {item['title'][:60]}")
                summary = summarize(item["title"], item["desc"])
                cat_arts.append({
                    "cat": cat,
                    "title": item["title"],
                    "sum": summary,
                    "src": feed.split("/")[2].replace("www.",""),
                    "age": time_ago(item["pub"]),
                    "url": item["url"],
                    "date": datetime.now().strftime("%B %d, %Y"),
                })
                seen.add(item["title"])
                time.sleep(0.5)
        today.extend(cat_arts)
        print(f"  → {len(cat_arts)} articles")

    print(f"\n✅ Today: {len(today)} | Archive: {len(archive)}")

    # Save articles.json
    new_data = {"today":today,"archive":archive,"updated":datetime.now().isoformat()}
    gh_put("articles.json", json.dumps(new_data,indent=2),
           f"Auto-update {datetime.now().strftime('%Y-%m-%d %H:%M')}", articles_sha)
    print("✅ articles.json saved!")

    # Generate index.html with articles baked in
    index_existing = gh_get("index.html")
    if index_existing:
        html = base64.b64decode(index_existing["content"]).decode()
        index_sha = index_existing["sha"]
        # Replace the data injection point
        articles_js = f"window.__ARTICLES__={json.dumps(today)};window.__ARCHIVE__={json.dumps(archive)};"
        if "window.__ARTICLES__" in html:
            html = re.sub(r"window\.__ARTICLES__=.*?;window\.__ARCHIVE__=.*?;", articles_js, html)
        else:
            html = html.replace("</head>", f"<script>{articles_js}</script></head>")
        gh_put("index.html", html, f"Inject articles {datetime.now().strftime('%Y-%m-%d %H:%M')}", index_sha)
        print("✅ index.html updated with fresh articles!")

if __name__ == "__main__":
    run()
