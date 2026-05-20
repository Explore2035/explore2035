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

def build_html(today, archive):
    """Build complete standalone HTML with articles baked in"""
    tl={"ai":"AI & ML","robotics":"ROBOTICS","biotech":"BIOTECH","space":"SPACE","gadgets":"GADGETS",
        "ev":"EV & TRANSPORT","fintech":"FINTECH","climate":"CLIMATE","gaming":"GAMING",
        "cyber":"CYBERSECURITY","smarthome":"SMART HOME","drones":"DRONES","longevity":"LONGEVITY","hair":"HAIR & RESTORATION"}
    tc={"ai":"tag-ai","robotics":"tag-robotics","biotech":"tag-biotech","space":"tag-space","gadgets":"tag-gadgets",
        "ev":"tag-ev","fintech":"tag-fintech","climate":"tag-climate","gaming":"tag-gaming",
        "cyber":"tag-cyber","smarthome":"tag-smarthome","drones":"tag-drones","longevity":"tag-longevity","hair":"tag-hair"}

    def card(a,i,delay=True):
        return f'''<div class="card">
      <span class="card-tag {tc.get(a["cat"],"tag-ai")}">{tl.get(a["cat"],a["cat"])}</span>
      <p class="card-title">{a["title"]}</p>
      <p class="card-sum">{a["sum"]}</p>
      <div class="card-footer">
        <span class="card-source">{a["src"]} · {a["age"]}</span>
        <div class="card-btns">
          <button class="card-btn shop" onclick="showPage(\'shop\')">🛒 SHOP</button>
          <a href="{a["url"]}" target="_blank" rel="noopener" class="card-btn">READ ↗</a>
        </div>
      </div>
    </div>'''

    # Group archive by date
    archive_html = ""
    grouped = {}
    for a in archive:
        d = a.get("date","Earlier")
        if d not in grouped: grouped[d]=[]
        grouped[d].append(a)
    for date, arts in grouped.items():
        archive_html += f'<p class="archive-title">⬡ {date}</p><div class="archive-grid">'
        for a in arts:
            archive_html += f'''<div class="archive-card">
          <p class="archive-card-title">{a["title"]}</p>
          <div class="archive-card-meta">
            <span class="card-tag {tc.get(a["cat"],"tag-ai")}" style="font-size:8px;padding:2px 6px;">{tl.get(a["cat"],a["cat"])}</span>
            <span>{a["src"]}</span>
          </div>
        </div>'''
        archive_html += '</div>'

    featured = today[0] if today else None
    feat_html = ""
    if featured:
        feat_html = f'''<p class="feat-label">⬡ FEATURED STORY</p>
    <p class="feat-title">{featured["title"]}</p>
    <p class="feat-body">{featured["sum"]}</p>
    <div class="feat-meta">
      <span>{featured["src"]} · {featured["age"]}</span>
      <a href="{featured["url"]}" target="_blank" rel="noopener" class="feat-btn">READ MORE ↗</a>
      <button class="feat-btn" onclick="showPage(\'shop\')">🛒 SHOP RELATED ↗</button>
    </div>'''

    all_cards = "".join([card(a,i) for i,a in enumerate(today[1:])])
    today_json = json.dumps(today)
    archive_json = json.dumps(archive)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Explore2035 — The Future Is Closer Than You Think</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Inter:wght@300;400;500&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#050A14;font-family:'Inter',sans-serif;color:#e2e8f0;overflow-x:hidden;}}
:root{{--teal:#00FFB2;--teal2:#00C896;--blue:#0af;--purple:#a78bfa;--dark:#050A14;--card:#0D1F3C;--border:rgba(0,255,178,0.15);}}
#bgc{{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;}}
#intro{{position:fixed;top:0;left:0;width:100%;height:100%;background:#000;z-index:100;overflow:hidden;}}
#intro-canvas{{position:absolute;top:0;left:0;width:100%;height:100%;}}
#skip-btn{{position:absolute;bottom:22px;right:22px;font-family:'Orbitron',monospace;font-size:11px;color:#00FFB2;background:rgba(0,255,178,0.08);border:0.5px solid #00FFB2;border-radius:3px;padding:9px 20px;cursor:pointer;letter-spacing:0.08em;z-index:10;}}
#skip-btn:hover{{background:rgba(0,255,178,0.18);}}
#site{{display:none;position:relative;z-index:1;min-height:100vh;}}
.hdr{{display:flex;justify-content:space-between;align-items:center;padding:1rem 1.5rem 0.75rem;border-bottom:0.5px solid var(--border);position:sticky;top:0;background:rgba(5,10,20,0.95);backdrop-filter:blur(10px);z-index:50;}}
.logo{{font-family:'Orbitron',monospace;font-size:20px;font-weight:900;color:#fff;letter-spacing:2px;cursor:pointer;text-decoration:none;}}
.logo span{{color:var(--teal);text-shadow:0 0 20px var(--teal);}}
.hdr-right{{display:flex;align-items:center;gap:12px;}}
.live-dot{{width:7px;height:7px;border-radius:50%;background:var(--teal);box-shadow:0 0 8px var(--teal);animation:pulse 2s infinite;}}
@keyframes pulse{{0%,100%{{opacity:1;}}50%{{opacity:0.3;}}}}
.theme-btn{{background:rgba(0,255,178,0.05);border:0.5px solid var(--border);border-radius:20px;padding:5px 14px;color:var(--teal);font-size:11px;cursor:pointer;font-family:'Orbitron',monospace;}}
.hdr-time{{font-size:10px;color:#475569;font-family:'Orbitron',monospace;}}
.nav{{display:flex;gap:4px;padding:0.75rem 1.5rem;border-bottom:0.5px solid var(--border);background:rgba(5,10,20,0.9);flex-wrap:wrap;}}
.nav-btn{{font-size:11px;padding:6px 14px;border:0.5px solid transparent;border-radius:4px;background:none;cursor:pointer;color:#64748b;font-family:'Orbitron',monospace;letter-spacing:0.04em;transition:all 0.2s;}}
.nav-btn:hover{{color:var(--teal);}}
.nav-btn.active{{color:var(--teal);border-color:var(--teal);background:rgba(0,255,178,0.05);}}
.hero{{padding:3rem 1.5rem 2rem;text-align:center;}}
.hero-label{{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:0.2em;color:var(--teal);margin-bottom:14px;text-transform:uppercase;}}
.hero-title{{font-family:'Orbitron',monospace;font-size:clamp(20px,4vw,36px);font-weight:900;line-height:1.2;margin-bottom:14px;color:#fff;}}
.hero-title span{{color:var(--teal);text-shadow:0 0 30px var(--teal);}}
.hero-sub{{font-size:14px;color:#64748b;line-height:1.7;max-width:540px;margin:0 auto 2rem;}}
.hero-search{{display:flex;gap:8px;max-width:500px;margin:0 auto;}}
.hero-search input{{flex:1;background:rgba(255,255,255,0.04);border:0.5px solid var(--border);border-radius:4px;padding:11px 16px;color:#e2e8f0;font-family:inherit;font-size:13px;}}
.hero-search input::placeholder{{color:#334155;}}
.hero-search input:focus{{outline:none;border-color:var(--teal);}}
.hero-search button{{padding:11px 22px;background:var(--teal);color:#050A14;border:none;border-radius:4px;cursor:pointer;font-family:'Orbitron',monospace;font-size:11px;font-weight:700;}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:0 1.5rem 1.5rem;max-width:800px;margin:0 auto;}}
.stat{{background:var(--card);border:0.5px solid var(--border);border-radius:8px;padding:0.85rem 1rem;text-align:center;}}
.stat:hover{{border-color:var(--teal);}}
.stat-num{{font-family:'Orbitron',monospace;font-size:22px;font-weight:700;color:var(--teal);}}
.stat-label{{font-size:10px;color:#475569;letter-spacing:0.05em;text-transform:uppercase;margin-top:3px;}}
.cats{{display:flex;gap:6px;flex-wrap:wrap;padding:0 1.5rem 1rem;}}
.cat{{font-size:10px;padding:5px 12px;border-radius:3px;border:0.5px solid var(--border);background:transparent;cursor:pointer;color:#64748b;font-family:'Orbitron',monospace;letter-spacing:0.03em;transition:all 0.15s;}}
.cat:hover{{border-color:var(--teal);color:var(--teal);}}
.cat.active{{background:rgba(0,255,178,0.08);border-color:var(--teal);color:var(--teal);}}
.featured{{margin:0 1.5rem 1.5rem;background:var(--card);border:0.5px solid var(--border);border-radius:10px;padding:1.5rem;position:relative;overflow:hidden;}}
.featured::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--teal),transparent);}}
.feat-label{{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:0.15em;color:var(--teal);margin-bottom:10px;}}
.feat-title{{font-family:'Orbitron',monospace;font-size:16px;font-weight:700;line-height:1.4;margin-bottom:10px;color:#fff;}}
.feat-body{{font-size:13px;color:#64748b;line-height:1.7;margin-bottom:14px;}}
.feat-meta{{font-size:11px;color:#334155;display:flex;gap:12px;align-items:center;flex-wrap:wrap;}}
.feat-btn{{font-size:10px;color:var(--teal);background:none;border:0.5px solid var(--teal);border-radius:3px;padding:4px 10px;cursor:pointer;font-family:'Orbitron',monospace;text-decoration:none;display:inline-block;}}
.sec-title{{font-family:'Orbitron',monospace;font-size:11px;letter-spacing:0.1em;color:#334155;padding:0 1.5rem 0.75rem;text-transform:uppercase;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;padding:0 1.5rem 2rem;}}
.card{{background:var(--card);border:0.5px solid var(--border);border-radius:8px;padding:1.1rem 1.2rem;cursor:pointer;transition:border-color 0.2s,transform 0.2s,box-shadow 0.2s;opacity:1;}}
.card:hover{{border-color:rgba(0,255,178,0.4);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,0.3);}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(14px);}}to{{opacity:1;transform:translateY(0);}}}}
.card-tag{{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;padding:3px 8px;border-radius:3px;display:inline-block;margin-bottom:8px;font-family:'Orbitron',monospace;}}
.tag-ai{{background:rgba(0,255,178,0.08);color:#00FFB2;border:0.5px solid rgba(0,255,178,0.25);}}
.tag-robotics{{background:rgba(10,170,255,0.08);color:#0af;border:0.5px solid rgba(10,170,255,0.25);}}
.tag-biotech{{background:rgba(251,191,36,0.08);color:#fbbf24;border:0.5px solid rgba(251,191,36,0.25);}}
.tag-space{{background:rgba(167,139,250,0.08);color:#a78bfa;border:0.5px solid rgba(167,139,250,0.25);}}
.tag-gadgets{{background:rgba(251,113,133,0.08);color:#fb7185;border:0.5px solid rgba(251,113,133,0.25);}}
.tag-ev{{background:rgba(52,211,153,0.08);color:#34d399;border:0.5px solid rgba(52,211,153,0.25);}}
.tag-fintech{{background:rgba(251,191,36,0.08);color:#f59e0b;border:0.5px solid rgba(251,191,36,0.25);}}
.tag-climate{{background:rgba(16,185,129,0.08);color:#10b981;border:0.5px solid rgba(16,185,129,0.25);}}
.tag-gaming{{background:rgba(139,92,246,0.08);color:#8b5cf6;border:0.5px solid rgba(139,92,246,0.25);}}
.tag-cyber{{background:rgba(239,68,68,0.08);color:#ef4444;border:0.5px solid rgba(239,68,68,0.25);}}
.tag-smarthome{{background:rgba(6,182,212,0.08);color:#06b6d4;border:0.5px solid rgba(6,182,212,0.25);}}
.tag-drones{{background:rgba(245,158,11,0.08);color:#f59e0b;border:0.5px solid rgba(245,158,11,0.25);}}
.tag-longevity{{background:rgba(236,72,153,0.08);color:#ec4899;border:0.5px solid rgba(236,72,153,0.25);}}
.tag-hair{{background:rgba(168,85,247,0.08);color:#a855f7;border:0.5px solid rgba(168,85,247,0.25);}}
.card-title{{font-size:14px;font-weight:500;line-height:1.45;margin-bottom:7px;color:#e2e8f0;}}
.card-sum{{font-size:12px;color:#475569;line-height:1.6;margin-bottom:10px;}}
.card-footer{{display:flex;justify-content:space-between;align-items:center;}}
.card-source{{font-size:10px;color:#334155;font-family:'Orbitron',monospace;}}
.card-btns{{display:flex;gap:8px;}}
.card-btn{{font-size:10px;color:var(--teal);border:none;background:none;cursor:pointer;font-family:'Orbitron',monospace;padding:0;text-decoration:none;display:inline-block;}}
.card-btn.shop{{color:#fb7185;}}
.archive-section{{padding:0 1.5rem 2rem;}}
.archive-title{{font-family:'Orbitron',monospace;font-size:11px;letter-spacing:0.1em;color:#334155;margin-bottom:1rem;text-transform:uppercase;border-top:0.5px solid var(--border);padding-top:1.5rem;}}
.archive-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px;margin-bottom:1rem;}}
.archive-card{{background:rgba(13,31,60,0.5);border:0.5px solid rgba(0,255,178,0.08);border-radius:8px;padding:0.85rem 1rem;transition:all 0.2s;}}
.archive-card:hover{{border-color:rgba(0,255,178,0.3);}}
.archive-card-title{{font-size:13px;font-weight:500;color:#94a3b8;margin-bottom:6px;line-height:1.4;}}
.archive-card-meta{{font-size:10px;color:#334155;font-family:'Orbitron',monospace;display:flex;justify-content:space-between;align-items:center;}}
.shop-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;padding:0 1.5rem 2rem;}}
.shop-card{{background:var(--card);border:0.5px solid var(--border);border-radius:8px;overflow:hidden;transition:border-color 0.2s,transform 0.2s,box-shadow 0.2s;}}
.shop-card:hover{{border-color:rgba(0,255,178,0.4);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,0.3);}}
.shop-img{{height:110px;display:flex;align-items:center;justify-content:center;font-size:44px;background:rgba(255,255,255,0.02);border-bottom:0.5px solid var(--border);position:relative;}}
.shop-img::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--teal),transparent);}}
.shop-body{{padding:1rem 1.2rem;}}
.shop-name{{font-size:14px;font-weight:500;margin-bottom:4px;color:#e2e8f0;}}
.shop-desc{{font-size:11px;color:#475569;line-height:1.5;margin-bottom:8px;}}
.shop-rating{{display:flex;align-items:center;gap:6px;margin-bottom:8px;}}
.stars{{color:#fbbf24;font-size:12px;}}
.r-count{{font-size:10px;color:#334155;}}
.prices{{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:10px;}}
.price-tag{{font-size:11px;padding:3px 8px;border-radius:3px;border:0.5px solid var(--border);color:#64748b;}}
.price-best{{border-color:var(--teal);color:var(--teal);background:rgba(0,255,178,0.05);}}
.shop-btns{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;}}
.sbtn{{font-size:10px;padding:5px 10px;border-radius:3px;border:0.5px solid var(--border);cursor:pointer;background:none;color:#64748b;font-family:'Orbitron',monospace;transition:all 0.15s;}}
.sbtn:hover{{border-color:var(--teal);color:var(--teal);}}
.sbtn.primary{{background:var(--teal);color:#050A14;border-color:var(--teal);font-weight:700;}}
.shop-extras{{display:flex;gap:10px;}}
.sxbtn{{font-size:10px;color:#334155;background:none;border:none;cursor:pointer;font-family:inherit;}}
.sxbtn:hover{{color:var(--teal);}}
.filter-bar{{display:flex;gap:6px;flex-wrap:wrap;padding:0 1.5rem 1rem;align-items:center;}}
.filter-label{{font-size:10px;color:#334155;font-family:'Orbitron',monospace;letter-spacing:0.05em;}}
.about-wrap{{padding:1.5rem;}}
.about-card{{background:var(--card);border:0.5px solid var(--border);border-radius:10px;padding:1.5rem;margin-bottom:1rem;position:relative;overflow:hidden;}}
.about-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--teal),transparent);}}
.about-title{{font-family:'Orbitron',monospace;font-size:12px;color:var(--teal);letter-spacing:0.1em;margin-bottom:10px;}}
.about-text{{font-size:13px;color:#64748b;line-height:1.8;}}
.about-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-top:1rem;}}
.about-item{{background:rgba(0,255,178,0.03);border:0.5px solid var(--border);border-radius:6px;padding:0.85rem;text-align:center;}}
.about-icon{{font-size:24px;margin-bottom:6px;}}
.about-item-title{{font-family:'Orbitron',monospace;font-size:9px;color:var(--teal);margin-bottom:3px;}}
.about-item-text{{font-size:10px;color:#475569;line-height:1.4;}}
.newsletter{{margin:0 1.5rem 2rem;background:var(--card);border:0.5px solid var(--border);border-radius:10px;padding:1.5rem;text-align:center;position:relative;overflow:hidden;}}
.newsletter::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--teal),transparent);}}
.nl-title{{font-family:'Orbitron',monospace;font-size:14px;color:#fff;margin-bottom:6px;}}
.nl-sub{{font-size:12px;color:#475569;margin-bottom:14px;}}
.nl-form{{display:flex;gap:8px;max-width:420px;margin:0 auto;}}
.nl-form input{{flex:1;background:rgba(255,255,255,0.04);border:0.5px solid var(--border);border-radius:4px;padding:9px 14px;color:#e2e8f0;font-family:inherit;font-size:12px;}}
.nl-form input::placeholder{{color:#334155;}}
.nl-form button{{padding:9px 18px;background:var(--teal);color:#050A14;border:none;border-radius:4px;cursor:pointer;font-family:'Orbitron',monospace;font-size:10px;font-weight:700;white-space:nowrap;}}
.footer{{border-top:0.5px solid var(--border);padding:2rem 1.5rem;text-align:center;}}
.footer-logo{{font-family:'Orbitron',monospace;font-size:18px;font-weight:900;color:#fff;margin-bottom:8px;}}
.footer-logo span{{color:var(--teal);}}
.footer-text{{font-size:11px;color:#334155;margin-bottom:12px;}}
.footer-links{{display:flex;gap:20px;justify-content:center;flex-wrap:wrap;}}
.footer-link{{font-size:10px;color:#475569;font-family:'Orbitron',monospace;cursor:pointer;letter-spacing:0.05em;}}
.footer-link:hover{{color:var(--teal);}}
body.light{{background:#f0f4ff;color:#0a1628;}}
body.light #bgc{{opacity:0.15;}}
body.light .hdr{{background:rgba(240,244,255,0.95);}}
body.light .card,body.light .featured,body.light .shop-card,body.light .about-card,body.light .newsletter,body.light .stat{{background:#fff;border-color:rgba(0,150,100,0.2);}}
body.light .card-title,body.light .shop-name,body.light .feat-title{{color:#0a1628;}}
body.light .card-sum,body.light .shop-desc,body.light .feat-body,body.light .about-text,body.light .hero-sub{{color:#475569;}}
body.light .logo{{color:#0a1628;}}
body.light .archive-card{{background:rgba(255,255,255,0.8);}}
body.light .archive-card-title{{color:#334155;}}
.hidden{{display:none;}}
</style>
</head>
<body>
<canvas id="bgc"></canvas>
<div id="intro">
  <canvas id="intro-canvas"></canvas>
  <button id="skip-btn" onclick="skipIntro()">SKIP INTRO ↓</button>
</div>
<div id="site">
  <div class="hdr">
    <div style="display:flex;align-items:center;gap:10px;">
      <div class="live-dot"></div>
      <a class="logo" onclick="showPage('news')">EXPLORE<span>2035</span></a>
    </div>
    <div class="hdr-right">
      <span class="hdr-time" id="tn-time"></span>
      <button class="theme-btn" onclick="toggleTheme()" id="theme-btn">☀ LIGHT</button>
    </div>
  </div>
  <div class="nav">
    <button class="nav-btn active" id="btn-news" onclick="showPage('news')">⬡ NEWS</button>
    <button class="nav-btn" id="btn-shop" onclick="showPage('shop')">⬡ SHOP</button>
    <button class="nav-btn" id="btn-archive" onclick="showPage('archive')">⬡ ARCHIVE</button>
    <button class="nav-btn" id="btn-about" onclick="showPage('about')">⬡ ABOUT</button>
  </div>
  <div id="page-news">
    <div class="hero">
      <p class="hero-label">⬡ Live Intelligence Feed — Updated Daily at 6AM</p>
      <h1 class="hero-title">Exploring the <span>Future</span><br>One Breakthrough at a Time</h1>
      <p class="hero-sub">AI, robotics, biotech, space, gadgets, EVs, climate, longevity and more — 14 categories, powered by AI, updated every 24 hours.</p>
      <div class="hero-search">
        <input type="text" id="srch" placeholder="Search any technology, invention or topic..."/>
        <button onclick="doSearch()">SEARCH</button>
      </div>
    </div>
    <div class="stats">
      <div class="stat"><div class="stat-num">14</div><div class="stat-label">Categories</div></div>
      <div class="stat"><div class="stat-num">{len(today)}</div><div class="stat-label">Live Stories</div></div>
      <div class="stat"><div class="stat-num">24H</div><div class="stat-label">Update Cycle</div></div>
      <div class="stat"><div class="stat-num">{len(archive)}</div><div class="stat-label">Archived</div></div>
    </div>
    <div class="cats" id="news-cats">
      <button class="cat active" onclick="setCat('all',this)">ALL</button>
      <button class="cat" onclick="setCat('ai',this)">🧠 AI & ML</button>
      <button class="cat" onclick="setCat('robotics',this)">🤖 ROBOTICS</button>
      <button class="cat" onclick="setCat('biotech',this)">🧬 BIOTECH</button>
      <button class="cat" onclick="setCat('space',this)">🚀 SPACE</button>
      <button class="cat" onclick="setCat('gadgets',this)">📱 GADGETS</button>
      <button class="cat" onclick="setCat('ev',this)">🚗 EV & TRANSPORT</button>
      <button class="cat" onclick="setCat('fintech',this)">💰 FINTECH</button>
      <button class="cat" onclick="setCat('climate',this)">🌱 CLIMATE</button>
      <button class="cat" onclick="setCat('gaming',this)">🎮 GAMING</button>
      <button class="cat" onclick="setCat('cyber',this)">🔒 CYBERSECURITY</button>
      <button class="cat" onclick="setCat('smarthome',this)">🏠 SMART HOME</button>
      <button class="cat" onclick="setCat('drones',this)">✈️ DRONES</button>
      <button class="cat" onclick="setCat('longevity',this)">⏳ LONGEVITY</button>
      <button class="cat" onclick="setCat('hair',this)">💈 HAIR & RESTORATION</button>
    </div>
    <div class="featured" id="featured">{feat_html}</div>
    <p class="sec-title" id="sec-label">⬡ TODAY'S TOP STORIES</p>
    <div class="grid" id="news-grid">{all_cards}</div>
    <div class="newsletter">
      <p class="nl-title">⬡ STAY AHEAD OF THE FUTURE</p>
      <p class="nl-sub">Get the top breakthroughs across all 14 categories delivered to your inbox every morning. Free forever.</p>
      <div class="nl-form">
        <input type="email" placeholder="your@email.com"/>
        <button onclick="alert('Newsletter coming soon!')">SUBSCRIBE ↗</button>
      </div>
    </div>
  </div>
  <div id="page-shop" class="hidden">
    <div class="hero" style="padding-bottom:1rem;">
      <p class="hero-label">⬡ Shop & Discover</p>
      <h1 class="hero-title">The <span>Latest</span> Tech<br>Products of 2035</h1>
      <p class="hero-sub">Compare prices, read reviews, watch demos, and get full setup guides.</p>
    </div>
    <div class="filter-bar" id="shop-cats">
      <span class="filter-label">FILTER:</span>
      <button class="cat active" onclick="setShopCat('all',this)">ALL</button>
      <button class="cat" onclick="setShopCat('robotics',this)">ROBOTICS</button>
      <button class="cat" onclick="setShopCat('gadgets',this)">GADGETS</button>
      <button class="cat" onclick="setShopCat('biotech',this)">BIOTECH</button>
      <button class="cat" onclick="setShopCat('space',this)">SPACE</button>
      <button class="cat" onclick="setShopCat('ai',this)">AI</button>
      <button class="cat" onclick="setShopCat('ev',this)">EV</button>
      <button class="cat" onclick="setShopCat('smarthome',this)">SMART HOME</button>
      <button class="cat" onclick="setShopCat('hair',this)">HAIR</button>
    </div>
    <div class="shop-grid" id="shop-grid"></div>
  </div>
  <div id="page-archive" class="hidden">
    <div class="hero" style="padding-bottom:1rem;">
      <p class="hero-label">⬡ Story Archive</p>
      <h1 class="hero-title">Every Story <span>Ever</span><br>Published Here</h1>
      <p class="hero-sub">Our complete library of AI-curated technology breakthroughs.</p>
      <div class="hero-search" style="margin-top:1rem;">
        <input type="text" id="archive-srch" placeholder="Search the full archive..."/>
        <button onclick="doArchiveSearch()">SEARCH</button>
      </div>
    </div>
    <div class="archive-section" id="archive-section">{archive_html if archive_html else '<div style="padding:2rem;color:#475569;font-family:Orbitron,monospace;font-size:12px;text-align:center;">ARCHIVE GROWS DAILY — CHECK BACK SOON!</div>'}</div>
  </div>
  <div id="page-about" class="hidden">
    <div class="hero" style="padding-bottom:1rem;">
      <p class="hero-label">⬡ Our Mission</p>
      <h1 class="hero-title">Built for the <span>Curious</span><br>Minds of Tomorrow</h1>
      <p class="hero-sub">Explore2035 exists to make the future accessible to everyone.</p>
    </div>
    <div class="about-wrap">
      <div class="about-card">
        <p class="about-title">⬡ WHAT IS EXPLORE2035?</p>
        <p class="about-text">Explore2035 is a fully automated AI-powered technology discovery platform. Every 24 hours our pipeline fetches breaking news from trusted sources, uses Claude AI to write clear summaries, and publishes fresh stories across 14 categories.</p>
        <div class="about-grid">
          <div class="about-item"><div class="about-icon">🧠</div><div class="about-item-title">AI & ML</div><div class="about-item-text">Models changing everything</div></div>
          <div class="about-item"><div class="about-icon">🤖</div><div class="about-item-title">ROBOTICS</div><div class="about-item-text">Humanoids & automation</div></div>
          <div class="about-item"><div class="about-icon">🧬</div><div class="about-item-title">BIOTECH</div><div class="about-item-text">Gene editing & medicine</div></div>
          <div class="about-item"><div class="about-icon">🚀</div><div class="about-item-title">SPACE</div><div class="about-item-text">Mars & beyond</div></div>
          <div class="about-item"><div class="about-icon">📱</div><div class="about-item-title">GADGETS</div><div class="about-item-text">Next-gen devices</div></div>
          <div class="about-item"><div class="about-icon">🚗</div><div class="about-item-title">EV & TRANSPORT</div><div class="about-item-text">Electric future</div></div>
          <div class="about-item"><div class="about-icon">💰</div><div class="about-item-title">FINTECH</div><div class="about-item-text">Money & crypto</div></div>
          <div class="about-item"><div class="about-icon">🌱</div><div class="about-item-title">CLIMATE</div><div class="about-item-text">Clean energy</div></div>
          <div class="about-item"><div class="about-icon">🎮</div><div class="about-item-title">GAMING</div><div class="about-item-text">Metaverse & VR</div></div>
          <div class="about-item"><div class="about-icon">🔒</div><div class="about-item-title">CYBERSECURITY</div><div class="about-item-text">Digital protection</div></div>
          <div class="about-item"><div class="about-icon">🏠</div><div class="about-item-title">SMART HOME</div><div class="about-item-text">Connected living</div></div>
          <div class="about-item"><div class="about-icon">✈️</div><div class="about-item-title">DRONES</div><div class="about-item-text">Aerial innovation</div></div>
          <div class="about-item"><div class="about-icon">⏳</div><div class="about-item-title">LONGEVITY</div><div class="about-item-text">Anti-aging science</div></div>
          <div class="about-item"><div class="about-icon">💈</div><div class="about-item-title">HAIR & RESTORATION</div><div class="about-item-text">Regrowth breakthroughs</div></div>
        </div>
      </div>
      <div class="about-card">
        <p class="about-title">⬡ HOW IT WORKS</p>
        <p class="about-text">Every day at 6AM our AI pipeline automatically fetches the latest tech news from 28 trusted RSS feeds, uses Claude AI to write clear plain-English summaries, categorizes each story, and publishes them here. Zero human involvement required.</p>
      </div>
    </div>
  </div>
  <div class="footer">
    <p class="footer-logo">EXPLORE<span>2035</span></p>
    <p class="footer-text">© 2035 Explore2035.com — The future is closer than you think</p>
    <div class="footer-links">
      <span class="footer-link" onclick="showPage('news')">NEWS</span>
      <span class="footer-link" onclick="showPage('shop')">SHOP</span>
      <span class="footer-link" onclick="showPage('archive')">ARCHIVE</span>
      <span class="footer-link" onclick="showPage('about')">ABOUT</span>
    </div>
  </div>
</div>
<script>
const ALL_ARTICLES={today_json};
const ARCHIVE={archive_json};
const tl={{ai:'AI & ML',robotics:'ROBOTICS',biotech:'BIOTECH',space:'SPACE',gadgets:'GADGETS',ev:'EV & TRANSPORT',fintech:'FINTECH',climate:'CLIMATE',gaming:'GAMING',cyber:'CYBERSECURITY',smarthome:'SMART HOME',drones:'DRONES',longevity:'LONGEVITY',hair:'HAIR & RESTORATION'}};
const tc={{ai:'tag-ai',robotics:'tag-robotics',biotech:'tag-biotech',space:'tag-space',gadgets:'tag-gadgets',ev:'tag-ev',fintech:'tag-fintech',climate:'tag-climate',gaming:'tag-gaming',cyber:'tag-cyber',smarthome:'tag-smarthome',drones:'tag-drones',longevity:'tag-longevity',hair:'tag-hair'}};

function setCat(cat,btn){{
  document.querySelectorAll('#news-cats .cat').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  const filtered=cat==='all'?ALL_ARTICLES:ALL_ARTICLES.filter(a=>a.cat===cat);
  document.getElementById('sec-label').textContent=`⬡ ${{cat==='all'?'TODAY\\'S TOP STORIES':tl[cat]+' — TODAY\\'S STORIES'}}`;
  if(filtered.length){{
    document.getElementById('featured').innerHTML=`
      <p class="feat-label">⬡ FEATURED STORY</p>
      <p class="feat-title">${{filtered[0].title}}</p>
      <p class="feat-body">${{filtered[0].sum}}</p>
      <div class="feat-meta">
        <span>${{filtered[0].src}} · ${{filtered[0].age}}</span>
        <a href="${{filtered[0].url}}" target="_blank" rel="noopener" class="feat-btn">READ MORE ↗</a>
        <button class="feat-btn" onclick="showPage('shop')">🛒 SHOP RELATED ↗</button>
      </div>`;
    document.getElementById('news-grid').innerHTML=filtered.slice(1).map((a,i)=>`
      <div class="card" style="animation-delay:${{i*0.04}}s">
        <span class="card-tag ${{tc[a.cat]||'tag-ai'}}">${{tl[a.cat]||a.cat}}</span>
        <p class="card-title">${{a.title}}</p>
        <p class="card-sum">${{a.sum}}</p>
        <div class="card-footer">
          <span class="card-source">${{a.src}} · ${{a.age}}</span>
          <div class="card-btns">
            <button class="card-btn shop" onclick="showPage('shop')">🛒 SHOP</button>
            <a href="${{a.url}}" target="_blank" rel="noopener" class="card-btn">READ ↗</a>
          </div>
        </div>
      </div>`).join('');
  }} else {{
    document.getElementById('featured').innerHTML='';
    document.getElementById('news-grid').innerHTML='<div style="padding:2rem;color:#475569;font-family:Orbitron,monospace;font-size:12px;text-align:center;">NO STORIES IN THIS CATEGORY TODAY</div>';
  }}
}}

function doSearch(){{
  const q=document.getElementById('srch').value.trim().toLowerCase();
  if(!q)return;
  const results=ALL_ARTICLES.filter(a=>a.title.toLowerCase().includes(q)||a.sum.toLowerCase().includes(q));
  document.getElementById('sec-label').textContent=`⬡ SEARCH: "${{q.toUpperCase()}}" — ${{results.length}} RESULTS`;
  document.getElementById('featured').innerHTML='';
  document.getElementById('news-grid').innerHTML=results.map((a,i)=>`
    <div class="card" style="animation-delay:${{i*0.04}}s">
      <span class="card-tag ${{tc[a.cat]||'tag-ai'}}">${{tl[a.cat]||a.cat}}</span>
      <p class="card-title">${{a.title}}</p>
      <p class="card-sum">${{a.sum}}</p>
      <div class="card-footer">
        <span class="card-source">${{a.src}} · ${{a.age}}</span>
        <div class="card-btns">
          <button class="card-btn shop" onclick="showPage('shop')">🛒 SHOP</button>
          <a href="${{a.url}}" target="_blank" rel="noopener" class="card-btn">READ ↗</a>
        </div>
      </div>
    </div>`).join('');
  document.querySelectorAll('#news-cats .cat').forEach(b=>b.classList.remove('active'));
}}
document.getElementById('srch').addEventListener('keydown',e=>{{if(e.key==='Enter')doSearch();}});

function doArchiveSearch(){{
  const q=document.getElementById('archive-srch').value.trim().toLowerCase();
  const results=q?ARCHIVE.filter(a=>a.title.toLowerCase().includes(q)||(a.cat||'').includes(q)):ARCHIVE;
  renderArchive(results);
}}
document.getElementById('archive-srch').addEventListener('keydown',e=>{{if(e.key==='Enter')doArchiveSearch();}});

function renderArchive(articles){{
  if(!articles.length){{document.getElementById('archive-section').innerHTML='<div style="padding:2rem;color:#475569;font-family:Orbitron,monospace;font-size:12px;text-align:center;">NO RESULTS FOUND</div>';return;}}
  const grouped={{}};
  articles.forEach(a=>{{const d=a.date||'Earlier';if(!grouped[d])grouped[d]=[];grouped[d].push(a);}});
  document.getElementById('archive-section').innerHTML=Object.entries(grouped).map(([date,arts])=>`
    <p class="archive-title">⬡ ${{date}}</p>
    <div class="archive-grid">${{arts.map(a=>`
      <div class="archive-card">
        <p class="archive-card-title">${{a.title}}</p>
        <div class="archive-card-meta">
          <span class="card-tag ${{tc[a.cat]||'tag-ai'}}" style="font-size:8px;padding:2px 6px;">${{tl[a.cat]||a.cat}}</span>
          <span>${{a.src}}</span>
        </div>
      </div>`).join('')}}</div>`).join('');
}}

const PRODUCTS=[
  {{cat:'robotics',e:'🤖',name:'Unitree G1 Humanoid Robot',desc:'Bipedal home assistant with 43 joints, AI vision, and voice control.',rating:4.7,rev:1240,prices:[{{s:'Amazon',p:'$16,999',b:true}},{{s:'Unitree',p:'$17,500'}},{{s:'B&H',p:'$17,200'}}]}},
  {{cat:'gadgets',e:'🥽',name:'Apple Vision Pro 2',desc:'Spatial computing headset with 4K per eye and full hand tracking.',rating:4.5,rev:8900,prices:[{{s:'Apple',p:'$2,999',b:true}},{{s:'Amazon',p:'$3,099'}},{{s:'Best Buy',p:'$3,049'}}]}},
  {{cat:'biotech',e:'🩺',name:'Withings Body Scan Scale',desc:'Medical-grade station measuring body composition and heart health.',rating:4.6,rev:3200,prices:[{{s:'Withings',p:'$399',b:true}},{{s:'Amazon',p:'$419'}},{{s:'Best Buy',p:'$409'}}]}},
  {{cat:'space',e:'☀️',name:'EcoFlow DELTA Pro 3',desc:'3,600Wh portable power with 2,600W solar input.',rating:4.8,rev:5600,prices:[{{s:'EcoFlow',p:'$3,199',b:true}},{{s:'Amazon',p:'$3,299'}},{{s:'Costco',p:'$3,150'}}]}},
  {{cat:'ai',e:'🧠',name:'Rabbit R2 AI Device',desc:'Pocket AI companion with natural language control of any app.',rating:4.2,rev:2100,prices:[{{s:'Rabbit',p:'$199',b:true}},{{s:'Amazon',p:'$219'}},{{s:'Best Buy',p:'$209'}}]}},
  {{cat:'gadgets',e:'📡',name:'Starlink Mini Kit',desc:'Portable satellite dish delivering 100Mbps+ anywhere on Earth.',rating:4.9,rev:12000,prices:[{{s:'Starlink',p:'$599',b:true}},{{s:'Amazon',p:'$649'}},{{s:'REI',p:'$629'}}]}},
  {{cat:'robotics',e:'🌀',name:'Dyson 360 Vis Nav Robot',desc:'360-degree vision robot vacuum with 2,800Pa suction.',rating:4.5,rev:4400,prices:[{{s:'Dyson',p:'$1,199',b:true}},{{s:'Amazon',p:'$1,249'}},{{s:'Best Buy',p:'$1,229'}}]}},
  {{cat:'biotech',e:'💍',name:'Oura Ring Gen 4',desc:'Health ring monitoring sleep, HRV, temperature, and readiness.',rating:4.7,rev:22000,prices:[{{s:'Oura',p:'$349',b:true}},{{s:'Amazon',p:'$359'}},{{s:'Best Buy',p:'$349'}}]}},
  {{cat:'ev',e:'⚡',name:'Tesla Model 3 Highland',desc:'Refreshed Model 3 with 358-mile range and new interior.',rating:4.8,rev:15000,prices:[{{s:'Tesla',p:'$40,240',b:true}},{{s:'Carvana',p:'$41,500'}},{{s:'AutoNation',p:'$42,000'}}]}},
  {{cat:'smarthome',e:'🏠',name:'Amazon Echo Hub',desc:'Smart home control panel with 8" display and Matter support.',rating:4.4,rev:6700,prices:[{{s:'Amazon',p:'$179',b:true}},{{s:'Best Buy',p:'$189'}},{{s:'Walmart',p:'$185'}}]}},
  {{cat:'hair',e:'💈',name:'iRestore Laser Hair Growth System',desc:'FDA-cleared laser helmet stimulating hair follicles with red light therapy.',rating:4.3,rev:8900,prices:[{{s:'iRestore',p:'$695',b:true}},{{s:'Amazon',p:'$749'}},{{s:'HSN',p:'$695'}}]}},
  {{cat:'hair',e:'🧴',name:'Hims Minoxidil Foam 5%',desc:'FDA-approved topical treatment clinically proven to regrow hair in men.',rating:4.5,rev:24000,prices:[{{s:'Hims',p:'$44/mo',b:true}},{{s:'Amazon',p:'$29'}},{{s:'CVS',p:'$32'}}]}},
];

function renderShop(cat){{
  const f=cat==='all'?PRODUCTS:PRODUCTS.filter(p=>p.cat===cat);
  document.getElementById('shop-grid').innerHTML=f.map((p,i)=>`
    <div class="shop-card">
      <div class="shop-img">${{p.e}}</div>
      <div class="shop-body">
        <span class="card-tag ${{tc[p.cat]}}">${{tl[p.cat]}}</span>
        <p class="shop-name">${{p.name}}</p>
        <p class="shop-desc">${{p.desc}}</p>
        <div class="shop-rating">
          <span class="stars">${{'★'.repeat(Math.floor(p.rating))+'☆'.repeat(5-Math.floor(p.rating))}}</span>
          <span style="font-size:12px;font-weight:500;">${{p.rating}}</span>
          <span class="r-count">(${{p.rev.toLocaleString()}})</span>
        </div>
        <div class="prices">${{p.prices.map(pr=>`<span class="price-tag ${{pr.b?'price-best':''}}">${{pr.s}} ${{pr.p}}${{pr.b?' ★':''}}</span>`).join('')}}</div>
        <div class="shop-btns">
          <button class="sbtn primary">BEST DEAL ↗</button>
          <button class="sbtn">HOW-TO</button>
          <button class="sbtn">▶ DEMO</button>
        </div>
        <div class="shop-extras">
          <button class="sxbtn">⇄ COMPARE</button>
          <button class="sxbtn">✦ REVIEWS</button>
        </div>
      </div>
    </div>`).join('');
}}

function setShopCat(cat,btn){{
  document.querySelectorAll('#shop-cats .cat').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');renderShop(cat);
}}

function showPage(page){{
  ['news','shop','archive','about'].forEach(p=>{{document.getElementById('page-'+p).classList.toggle('hidden',p!==page);}});
  ['news','shop','archive','about'].forEach(p=>{{document.getElementById('btn-'+p).classList.toggle('active',p===page);}});
  window.scrollTo(0,0);
  if(page==='archive')renderArchive(ARCHIVE);
}}

let light=false;
function toggleTheme(){{light=!light;document.body.classList.toggle('light',light);document.getElementById('theme-btn').textContent=light?'◑ DARK':'☀ LIGHT';}}
document.getElementById('tn-time').textContent=new Date().toLocaleDateString('en-US',{{month:'short',day:'numeric',year:'numeric'}});

// ── SLINKY INTRO ENGINE — BIG COILS → SNAP → LOGO ────────────────────────────
const ic=document.getElementById('intro-canvas');
const ictx=ic.getContext('2d');
let IW,IH;
function resizeIntro(){{ic.width=IW=window.innerWidth;ic.height=IH=window.innerHeight;}}
resizeIntro();
window.addEventListener('resize',resizeIntro);
const _lr=(a,b,t)=>a+(b-a)*t;
const _eo3=t=>1-Math.pow(1-t,3);
const _eo5=t=>1-Math.pow(1-t,5);
const _el=t=>t===0?0:t===1?1:Math.pow(2,-10*t)*Math.sin((t*10-.75)*(2*Math.PI)/3)+1;
const _cl=(v,a,b)=>Math.max(a,Math.min(b,v));
let _iparts=[],_ishocks=[];
function _iburst(x,y,n,spd,cols,r=3,g=.08){{for(let i=0;i<n;i++){{const a=Math.random()*Math.PI*2,s=spd*(.4+Math.random()*.6),col=cols[Math.floor(Math.random()*cols.length)];_iparts.push({{x,y,vx:Math.cos(a)*s,vy:Math.sin(a)*s,life:1,decay:.012+Math.random()*.02,r:r*(.5+Math.random()*.5),col,grav:g,tail:[]}});}}}}
function _iring(x,y,n,col,spd=14){{for(let i=0;i<n;i++){{const a=(Math.PI*2*i)/n;_iparts.push({{x,y,vx:Math.cos(a)*spd,vy:Math.sin(a)*spd,life:1,decay:.015+Math.random()*.01,r:3+Math.random()*3,col,grav:.03,tail:[]}});}}}}
function _ashock(x,y,col,mr){{_ishocks.push({{x,y,r:0,mr,col,life:1,decay:.022}});}}
let _ifl=0,_ifc='rgba(255,255,255,';
function _dofl(c,i=1){{_ifl=i;_ifc=c;}}
function _tickp(){{
  _iparts=_iparts.filter(p=>p.life>0);
  _iparts.forEach(p=>{{
    p.tail.push({{x:p.x,y:p.y}});if(p.tail.length>10)p.tail.shift();
    p.x+=p.vx;p.y+=p.vy;p.vy+=p.grav;p.vx*=.97;p.vy*=.97;p.life-=p.decay;p.r*=.97;
    if(p.tail.length>1){{ictx.beginPath();ictx.moveTo(p.tail[0].x,p.tail[0].y);p.tail.forEach(pt=>ictx.lineTo(pt.x,pt.y));ictx.strokeStyle=p.col.replace('1)',`${{p.life*.3}})`);ictx.lineWidth=p.r*.4;ictx.stroke();}}
    ictx.shadowBlur=14;ictx.shadowColor=p.col;ictx.beginPath();ictx.arc(p.x,p.y,Math.max(.1,p.r),0,Math.PI*2);ictx.fillStyle=p.col.replace('1)',`${{_cl(p.life,0,1)}}`+')');ictx.fill();ictx.shadowBlur=0;
  }});
}}
function _ticks(){{
  _ishocks=_ishocks.filter(s=>s.life>0);
  _ishocks.forEach(s=>{{s.r=_lr(0,s.mr,1-s.life);s.life-=s.decay;const a=_cl(s.life*.7,0,1);ictx.beginPath();ictx.arc(s.x,s.y,s.r,0,Math.PI*2);ictx.strokeStyle=s.col.replace('1)',`${{a}})`);ictx.lineWidth=4*s.life;ictx.shadowBlur=24;ictx.shadowColor=s.col;ictx.stroke();ictx.shadowBlur=0;}});
}}
let _istars=[];
function _initst(){{_istars=[];for(let i=0;i<120;i++)_istars.push({{x:Math.random()*IW,y:Math.random()*IH,r:Math.random()*1.4+.2,a:Math.random()*.5+.1,f:Math.random()*Math.PI*2}});}}
_initst();
const ICOILS=16;
function _getSpread(){{const m=IW*.05,pos=[];for(let i=0;i<=ICOILS;i++)pos.push(_lr(m,IW-m,i/ICOILS));return pos;}}
function _getCompress(t){{const m=IW*.05,pos=[];for(let i=0;i<=ICOILS;i++){{const fx=_lr(m,IW-m,i/ICOILS);pos.push(_lr(fx,IW/2,_eo5(t)));}}return pos;}}
function _dcoils(positions,ryv,alpha,wobble=0){{
  const N=positions.length-1;
  for(let i=0;i<N;i++){{
    const x1=positions[i],x2=positions[i+1],cx=(x1+x2)/2,rx=Math.abs(x2-x1)/2;
    if(rx<1)continue;
    const isBack=i%2===1;
    const wy=wobble>0?Math.sin(i*.8+Date.now()*.005)*wobble:0;
    const cy=IH/2+wy;
    ictx.shadowBlur=24;ictx.shadowColor='rgba(0,255,178,1)';
    ictx.beginPath();ictx.ellipse(cx,cy,rx,ryv,0,isBack?0:Math.PI,isBack?Math.PI:0);
    ictx.strokeStyle=`rgba(0,255,178,${{alpha*.2}})`;ictx.lineWidth=16;ictx.stroke();ictx.shadowBlur=0;
    ictx.shadowBlur=14;ictx.shadowColor='rgba(0,255,178,1)';
    ictx.beginPath();ictx.ellipse(cx,cy,rx,ryv,0,isBack?0:Math.PI,isBack?Math.PI:0);
    ictx.strokeStyle=`rgba(0,255,178,${{alpha*.45}})`;ictx.lineWidth=7;ictx.stroke();ictx.shadowBlur=0;
    ictx.shadowBlur=8;ictx.shadowColor='rgba(0,255,178,1)';
    ictx.beginPath();ictx.ellipse(cx,cy,rx,ryv,0,isBack?0:Math.PI,isBack?Math.PI:0);
    ictx.strokeStyle=`rgba(0,255,178,${{alpha*.95}})`;ictx.lineWidth=2.5;ictx.stroke();ictx.shadowBlur=0;
    ictx.beginPath();ictx.ellipse(cx,cy-ryv*.38,rx*.7,ryv*.18,0,Math.PI,0);
    ictx.strokeStyle=`rgba(255,255,255,${{alpha*.45}})`;ictx.lineWidth=1.5;ictx.stroke();
    ictx.shadowBlur=12;ictx.shadowColor='rgba(0,255,178,1)';
    ictx.beginPath();ictx.arc(x2,cy,4.5,0,Math.PI*2);
    ictx.fillStyle=`rgba(0,255,178,${{alpha*.9}})`;ictx.fill();ictx.shadowBlur=0;
  }}
}}
function _dlogo(alpha,scale,glitch){{
  if(alpha<=0)return;
  ictx.save();ictx.globalAlpha=_cl(alpha,0,1);ictx.translate(IW/2,IH/2);ictx.scale(scale,scale);
  const R=Math.min(IW,IH)*.30;
  const bg=ictx.createRadialGradient(0,0,0,0,0,R*1.5);bg.addColorStop(0,`rgba(0,255,178,${{alpha*.16}})`);bg.addColorStop(1,'rgba(0,0,0,0)');
  ictx.beginPath();ictx.arc(0,0,R*1.5,0,Math.PI*2);ictx.fillStyle=bg;ictx.fill();
  for(let ring=12;ring>=1;ring--){{ictx.shadowBlur=ring<3?20:4;ictx.shadowColor='rgba(0,255,178,.9)';ictx.beginPath();ictx.ellipse(0,0,R*(0.42+ring*.065),R*.1*(ring/12),0,0,Math.PI*2);ictx.strokeStyle=`rgba(0,255,178,${{(ring/12)*.92}})`;ictx.lineWidth=ring<3?3:1.5;ictx.stroke();ictx.shadowBlur=0;}}
  for(let p=0;p<4;p++){{ictx.shadowBlur=8+p*16;ictx.shadowColor='#00FFB2';ictx.beginPath();ictx.arc(0,0,R,0,Math.PI*2);ictx.strokeStyle=`rgba(0,255,178,${{.95-p*.2}})`;ictx.lineWidth=3.5-p*.6;ictx.stroke();}}ictx.shadowBlur=0;
  ictx.save();ictx.rotate(Date.now()/1800);ictx.setLineDash([10,14]);ictx.beginPath();ictx.arc(0,0,R*1.1,0,Math.PI*2);ictx.strokeStyle=`rgba(0,255,178,${{alpha*.35}})`;ictx.lineWidth=1.5;ictx.stroke();ictx.restore();ictx.setLineDash([]);
  ictx.save();ictx.rotate(-Date.now()/2800);ictx.setLineDash([4,20]);ictx.beginPath();ictx.arc(0,0,R*1.18,0,Math.PI*2);ictx.strokeStyle=`rgba(0,200,255,${{alpha*.2}})`;ictx.lineWidth=1;ictx.stroke();ictx.restore();ictx.setLineDash([]);
  [[0,-R],[R,0],[0,R],[-R,0]].forEach(([dx,dy])=>{{for(let p=0;p<3;p++){{ictx.beginPath();ictx.arc(dx,dy,8-p*2.5,0,Math.PI*2);ictx.fillStyle=`rgba(0,255,178,${{(.7-p*.2)*alpha}})`;ictx.shadowBlur=18;ictx.shadowColor='#00FFB2';ictx.fill();ictx.shadowBlur=0;}}}});
  const expSz=_cl(R*.36,18,52);
  if(glitch>0){{ictx.font=`900 ${{expSz}}px 'Orbitron',monospace`;ictx.textAlign='center';ictx.textBaseline='middle';ictx.fillStyle=`rgba(255,30,30,${{alpha*.55}})`;ictx.fillText('EXPLORE',-glitch*4,-R*.16+glitch*2);ictx.fillStyle=`rgba(30,30,255,${{alpha*.55}})`;ictx.fillText('EXPLORE',glitch*4,-R*.16-glitch*2);}}
  ictx.shadowBlur=24;ictx.shadowColor='rgba(255,255,255,.7)';ictx.font=`900 ${{expSz}}px 'Orbitron',monospace`;ictx.textAlign='center';ictx.textBaseline='middle';ictx.fillStyle=`rgba(255,255,255,${{alpha}})`;ictx.fillText('EXPLORE',0,-R*.16);ictx.shadowBlur=0;
  const numSz=_cl(R*.46,22,64);
  if(glitch>0){{ictx.font=`900 ${{numSz}}px 'Orbitron',monospace`;ictx.fillStyle=`rgba(255,30,30,${{alpha*.55}})`;ictx.fillText('2035',-glitch*5,R*.24+glitch);ictx.fillStyle=`rgba(30,100,255,${{alpha*.55}})`;ictx.fillText('2035',glitch*5,R*.24-glitch);}}
  for(let p=0;p<5;p++){{ictx.shadowBlur=6+p*14;ictx.shadowColor='#00FFB2';ictx.font=`900 ${{numSz}}px 'Orbitron',monospace`;ictx.fillStyle=`rgba(0,255,178,${{alpha*(1-p*.18)}})`;ictx.fillText('2035',0,R*.26);}}ictx.shadowBlur=0;
  ictx.font=`400 ${{_cl(R*.095,8,13)}}px 'Orbitron',monospace`;ictx.fillStyle=`rgba(120,150,170,${{alpha*.75}})`;ictx.fillText('THE FUTURE IS CLOSER THAN YOU THINK',0,R*.58);
  ictx.restore();
}}
let _iraf=null,_iph=0,_it=0,_ip0=0,_ip1=0,_ip2=0;
let _ila=0,_ils=.4,_ilg=0,_isn=false,_igrid=0,_isc=-1;
function _iframe(){{
  _it++;
  ictx.fillStyle='rgba(0,0,0,.82)';ictx.fillRect(0,0,IW,IH);
  if(_igrid>0){{ictx.strokeStyle=`rgba(0,255,178,${{_igrid*.07}})`;ictx.lineWidth=.5;for(let x=0;x<IW;x+=60){{ictx.beginPath();ictx.moveTo(x,0);ictx.lineTo(x,IH);ictx.stroke();}}for(let y=0;y<IH;y+=60){{ictx.beginPath();ictx.moveTo(0,y);ictx.lineTo(IW,y);ictx.stroke();}}_igrid=Math.max(0,_igrid-.012);}}
  _istars.forEach(s=>{{const a=s.a*(.7+.3*Math.sin(s.f+_it*.002));ictx.beginPath();ictx.arc(s.x,s.y,s.r,0,Math.PI*2);ictx.fillStyle=`rgba(255,255,255,${{a}})`;ictx.fill();}});
  if(_isc>=0){{const sg=ictx.createLinearGradient(0,_isc-40,0,_isc+40);sg.addColorStop(0,'rgba(0,255,178,0)');sg.addColorStop(.5,'rgba(0,255,178,.14)');sg.addColorStop(1,'rgba(0,255,178,0)');ictx.fillStyle=sg;ictx.fillRect(0,_isc-40,IW,80);_isc+=5;if(_isc>IH+50)_isc=-1;}}
  if(_iph===0){{
    // PHASE 0: Big coils fade in
    _ip0=Math.min(1,_ip0+.018);
    _dcoils(_getSpread(),IH*.42,_ip0,0);
    if(_ip0>=1)_iph=1;
  }} else if(_iph===1){{
    // PHASE 1: Breathe/wobble
    _ip1=Math.min(1,_ip1+.007);
    const ry=IH*.42+Math.sin(_it*.06)*IH*.025;
    _dcoils(_getSpread(),ry,1,3);
    if(Math.random()<.08){{const ci=Math.floor(Math.random()*ICOILS),m=IW*.05,cx=_lr(m,IW-m,ci/ICOILS);_iburst(cx,IH/2,2,2,['rgba(0,255,178,1)'],1.5,.03);}}
    if(_ip1>=1)_iph=2;
  }} else if(_iph===2){{
    // PHASE 2: Compress + SNAP
    _ip2=Math.min(1,_ip2+.012);
    const pos=_getCompress(_ip2);
    const ry=_lr(IH*.42,Math.min(IW,IH)*.30,_eo5(_ip2));
    _dcoils(pos,ry,1,0);
    if(Math.random()<.4){{const ci=Math.floor(Math.random()*ICOILS),m=IW*.05,px=_lr(_lr(m,IW-m,ci/ICOILS),IW/2,_eo5(_ip2));_iburst(px,IH/2+Math.random()*40-20,2,3,['rgba(0,255,178,1)','rgba(0,200,255,1)'],2,.05);}}
    if(_ip2>.92&&!_isn){{_isn=true;_dofl('rgba(0,255,178,',1.2);_ashock(IW/2,IH/2,'rgba(0,255,178,1)',IW*.8);_ashock(IW/2,IH/2,'rgba(100,200,255,1)',IW*.6);_ashock(IW/2,IH/2,'rgba(255,255,255,1)',IW*.35);_iburst(IW/2,IH/2,160,20,['rgba(0,255,178,1)','rgba(0,220,255,1)','rgba(255,255,255,1)','rgba(180,100,255,1)'],8,.07);_iburst(IW/2,IH/2,80,30,['rgba(0,255,178,1)','rgba(255,255,255,1)'],5,.1);_iring(IW/2,IH/2,56,'rgba(0,255,178,1)',16);_iring(IW/2,IH/2,36,'rgba(255,255,255,1)',26);_igrid=1;_isc=0;}}
    if(_ip2>.78){{const lt=(_ip2-.78)/.22;_ila=_eo3(lt);_ils=.35+_el(_cl(lt*1.4,0,1))*.65;_ilg=Math.max(0,(1-lt)*10);}}
    _dlogo(_ila,_ils,_ilg);
    if(_ip2>=1)_iph=3;
  }} else {{
    // PHASE 3: Hold
    _ilg=Math.max(0,_ilg-.15);
    const pulse=.97+Math.sin(_it*.025)*.03;
    if(Math.random()<.15){{const a=Math.random()*Math.PI*2,R=Math.min(IW,IH)*.32;_iburst(IW/2+Math.cos(a)*R,IH/2+Math.sin(a)*R,2,1.8,['rgba(0,255,178,1)','rgba(0,200,255,.9)'],1.8,.03);}}
    if(Math.random()<.004){{_ashock(IW/2,IH/2,'rgba(0,255,178,.5)',IW*.4);_iburst(IW/2,IH/2,20,6,['rgba(0,255,178,1)'],3,.05);}}
    _dlogo(1,pulse,_ilg*.25);
    if(_it>240)showSite();
  }}
  _tickp();_ticks();
  if(_ifl>0){{ictx.fillStyle=_ifc+_cl(_ifl*.8,0,1)+')';ictx.fillRect(0,0,IW,IH);_ifl-=.07;}}
  _iraf=requestAnimationFrame(_iframe);
}}
function showSite(){{
  if(_iraf)cancelAnimationFrame(_iraf);
  document.getElementById('intro').style.display='none';
  document.getElementById('site').style.display='block';
  initParticles();animParticles();
  setCat('all',document.querySelector('#news-cats .cat'));
}}
function skipIntro(){{if(_iraf)cancelAnimationFrame(_iraf);showSite();}}
// ── BG PARTICLES ──────────────────────────────────────────────────────────────
const canvas=document.getElementById('bgc');
const ctx=canvas.getContext('2d');
let W,H,particles=[];
function resize(){{W=canvas.width=window.innerWidth;H=canvas.height=window.innerHeight;}}
function Particle(){{this.x=Math.random()*W;this.y=Math.random()*H;this.r=Math.random()*1.2+0.3;this.vx=(Math.random()-0.5)*0.25;this.vy=(Math.random()-0.5)*0.25;this.a=Math.random()*0.4+0.1;}}
function initParticles(){{resize();particles=[];for(let i=0;i<80;i++)particles.push(new Particle());}}
function animParticles(){{
  ctx.clearRect(0,0,W,H);
  particles.forEach(p=>{{p.x+=p.vx;p.y+=p.vy;if(p.x<0||p.x>W)p.vx*=-1;if(p.y<0||p.y>H)p.vy*=-1;ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fillStyle=`rgba(0,255,178,${{p.a}})`;ctx.fill();}});
  particles.forEach((p,i)=>{{for(let j=i+1;j<particles.length;j++){{const dx=p.x-particles[j].x,dy=p.y-particles[j].y,d=Math.sqrt(dx*dx+dy*dy);if(d<100){{ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(particles[j].x,particles[j].y);ctx.strokeStyle=`rgba(0,255,178,${{0.05*(1-d/100)}})`;ctx.lineWidth=0.5;ctx.stroke();}}}}}});
  requestAnimationFrame(animParticles);
}}
window.addEventListener('resize',()=>{{if(particles.length)initParticles();}});
renderShop('all');
_initst();_iraf=requestAnimationFrame(_iframe);
</script>
</body>
</html>'''

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

    # Build and save complete index.html with articles baked in
    html = build_html(today, archive)
    index_existing = gh_get("index.html")
    index_sha = index_existing["sha"] if index_existing else None
    result = gh_put("index.html", html,
                    f"Inject articles {datetime.now().strftime('%Y-%m-%d %H:%M')}", index_sha)
    if result:
        print("✅ index.html rebuilt with fresh articles!")
    else:
        print("❌ Failed to update index.html")

if __name__ == "__main__":
    run()
