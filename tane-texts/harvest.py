"""Telifi dolmuş metinleri Vikikaynak'tan toplar; paragraf olarak kaydeder (seçim yerelde yapılır)."""
import json, re, sys, time, urllib.parse, urllib.request
from html.parser import HTMLParser

UA = {"User-Agent": "TaneTextHarvest/1.0 (dereliapps.github.io; educational diction app)"}

def api(wiki, **p):
    p.setdefault("format", "json")
    url = f"https://{wiki}.wikisource.org/w/api.php?" + urllib.parse.urlencode(p)
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(2 + 3 * i)
    return {}

class P(HTMLParser):
    SKIP = {"sup", "style", "table", "script"}
    def __init__(self):
        super().__init__(); self.paras = []; self.buf = None; self.skip = 0
    def handle_starttag(self, t, a):
        cls = dict(a).get("class", "") or ""
        if t in self.SKIP or "mw-editsection" in cls or "noprint" in cls or "ws-noexport" in cls or "reference" in cls or "poem" in cls:
            self.skip += 1; self._sk = getattr(self, "_sk", []) + [t]; return
        if t == "p" and not self.skip: self.buf = []
    def handle_endtag(self, t):
        if getattr(self, "_sk", None) and self._sk[-1] == t:
            self._sk.pop(); self.skip -= 1; return
        if t == "p" and self.buf is not None:
            s = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            if s: self.paras.append(s)
            self.buf = None
    def handle_data(self, d):
        if self.buf is not None and not self.skip: self.buf.append(d)

def paras(wiki, page):
    r = api(wiki, action="parse", prop="text", redirects=1, page=page)
    if "parse" not in r: return []
    p = P(); p.feed(r["parse"]["text"]["*"]); return p.paras

def subpages(wiki, prefix, limit=300):
    r = api(wiki, action="query", list="allpages", aplimit=limit, apprefix=prefix + "/")
    return [x["title"] for x in r.get("query", {}).get("allpages", [])]

def author_works(wiki, page):
    r = api(wiki, action="parse", prop="links", redirects=1, page=page)
    return [l["*"] for l in r.get("parse", {}).get("links", []) if l.get("ns") == 0 and "exists" in l]

def save(out):
    for wiki, recs in out.items():
        json.dump(recs, open(f"tane-texts/out_{wiki}.json", "w"), ensure_ascii=False)

def main():
    req = json.load(open("tane-texts/request.json"))
    out = {}
    budget = req.get("secondsPerJob", 420)
    for job in req["jobs"]:
        t0 = time.time()
        wiki, author = job["wiki"], job["author"]
        works = list(job.get("works", []))
        if job.get("authorPage"):
            works += [w for w in author_works(wiki, job["authorPage"]) if w not in works][: job.get("maxWorks", 80)]
        recs = out.setdefault(wiki, [])
        for w in works:
            pages = [w] + subpages(wiki, w)[: job.get("maxSub", 120)]
            for pg in pages:
                if time.time() - t0 > budget: break
                ps = paras(wiki, pg)
                if sum(len(x.split()) for x in ps) >= 80:
                    recs.append({"author": author, "work": w, "page": pg, "paras": ps})
                time.sleep(0.15)
            if time.time() - t0 > budget: break
        print(wiki, author, len(recs), round(time.time() - t0), flush=True)
        save(out)

main()
