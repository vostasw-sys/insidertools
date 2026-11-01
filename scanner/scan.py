"""Pemindai sinyal pra-rilis: kumpulkan -> deteksi -> petakan emiten -> skor -> JSON."""
import csv, json, re, time, hashlib, datetime as dt
from pathlib import Path
from urllib.parse import quote
import feedparser

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/data/signals.json"
NOW = dt.datetime.now(dt.timezone.utc)

ANON = ["sumber yang mengetahui", "menurut sumber", "informasi yang dihimpun", "tengah menjajaki",
        "sedang menjajaki", "mengincar", "people familiar", "sources said", "orang yang mengetahui",
        "sumber internal", "kabar yang beredar", "tengah mengkaji", "tengah mempersiapkan"]
CORP = ["akuisisi", "divestasi", "rights issue", "right issue", "private placement", "merger",
        "buyback", "tender offer", "go private", "pailit", "pkpu", "backdoor listing",
        "hmetd", "delisting", "stock split", "penjualan saham", "pengambilalihan"]
STANCE = {  # urutan prioritas
    "terkonfirmasi": ["membenarkan", "mengonfirmasi", "telah menandatangani", "confirmed"],
    "membantah": ["membantah", "menepis", "tidak benar", "belum ada rencana", "denied"],
    "tanpa komentar": ["enggan berkomentar", "tidak berkomentar", "declined to comment", "menolak berkomentar"],
    "menunggu jawaban": ["belum memberikan tanggapan", "belum menjawab", "belum merespons", "belum direspons"],
}
MEDIA_TIER = {"kontan": 20, "bisnis": 20, "bloomberg": 20, "reuters": 20, "katadata": 16, "cnbc": 18,
              "kompas": 14, "tempo": 14, "cnn indonesia": 14, "detik": 12, "emitennews": 12, "idx": 12}
FEEDS = []
SITES = ["kontan.co.id", "bisnis.com", "cnbcindonesia.com", "emitennews.com", "katadata.co.id", "investor.id", "idxchannel.com"]
STOP = {"IHSG", "BUMN", "RUPS", "PKPU", "KSEI", "IDXC", "OJK", "AMDK", "CEO", "LQ45", "IPO", "USD", "EBITDA", "ASEAN", "UMKM", "THR"}
RE_VALUE = re.compile(r"rp\s?([\d.,]+)\s?(triliun|miliar|juta)", re.I)
RE_UMA = re.compile(r"\buma\b|unusual market activity|permintaan penjelasan", re.I)
RE_SCHED = re.compile(r"(pekan depan|bulan depan|bulan ini|kuartal\s?[ivx1-4]+|semester|akhir tahun|dalam waktu dekat|\bq[1-4]\b)", re.I)
RE_PARTY = re.compile(r"\b(?:dengan|oleh|kepada)\s+(?:PT\s[A-Z]\w+|[A-Z][a-zA-Z]+\s(?:Group|Grup|Holdings?|Capital))")


def gnews(q):
    return f"https://news.google.com/rss/search?q={quote(q)}&hl=id&gl=ID&ceid=ID:id"


def queries():
    qs = [(gnews(f'"{p}" saham OR emiten when:7d'), p, None) for p in ANON[:7]]
    for c in ["akuisisi", "rights issue", "private placement", "divestasi", "PKPU", "buyback", "tender offer"]:
        qs.append((gnews(f"{c} emiten sumber when:7d"), None, c.lower()))
    corp_or = '(akuisisi OR "rights issue" OR "private placement" OR divestasi OR "tender offer" OR PKPU)'
    for d in SITES:
        qs.append((gnews(f"site:{d} {corp_or} saham when:7d"), None, None))
    for q in ["UMA BEI saham", '"unusual market activity" BEI saham', '"permintaan penjelasan" BEI saham']:
        qs.append((gnews(q + " when:14d"), None, "uma"))
    return qs


def load_emiten():
    rows = list(csv.DictReader(open(ROOT / "data/emiten.csv", encoding="utf-8")))
    pats = {}
    for r in rows:
        names = [r["name"].lower()] + [a.strip().lower() for a in r["aliases"].split("|") if a.strip()]
        pats[r["ticker"]] = [re.compile(rf"(?<!\w){re.escape(n)}(?!\w)") for n in names]
    return pats


def find_tickers(text, pats):
    low, found = text.lower(), set()
    for t, ps in pats.items():
        if any(p.search(low) for p in ps):
            found.add(t)
    for m in re.finditer(r"(?<![A-Z])([A-Z]{4})(?![A-Z])", text):
        if m.group(1) in pats:
            found.add(m.group(1))
    for m in re.finditer(r"\(([A-Z]{4})\)|\bsaham\s+([A-Z]{4})\b", text):
        code = m.group(1) or m.group(2)
        if code not in STOP:
            found.add(code)
    return sorted(found)


def idr_bn(text):
    best = 0.0
    for num, unit in RE_VALUE.findall(text):
        try:
            v = float(num.replace(".", "").replace(",", "."))
        except ValueError:
            continue
        best = max(best, v * {"triliun": 1000, "miliar": 1, "juta": 0.001}[unit.lower()])
    return best


def hits(text, words):
    low = text.lower()
    return [w for w in words if w in low]


def stance_of(text):
    for name, words in STANCE.items():
        if hits(text, words):
            return name
    return None


def fetch(url, default_media="", qanon=None, qcorp=None):
    out = []
    try:
        d = feedparser.parse(url, agent="Mozilla/5.0 (pemindai-pra-rilis research)")
    except Exception as e:
        print("gagal", url, e); return out
    for e in d.entries:
        pp = e.get("published_parsed") or e.get("updated_parsed")
        if not pp:
            continue
        title = re.sub(r"<[^>]+>", "", e.get("title", ""))
        media = (e.get("source") or {}).get("title") or default_media
        if " - " in title and (e.get("source") or {}).get("title"):
            title = title.rsplit(" - ", 1)[0]
        summ = re.sub(r"<[^>]+>", " ", e.get("summary", ""))
        out.append(dict(title=title.strip(), url=e.get("link", ""), media=media.strip(),
                        published=dt.datetime(*pp[:6], tzinfo=dt.timezone.utc).isoformat(),
                        text=f"{title}. {summ}".strip(), qanon=qanon, qcorp=qcorp))
    print(len(out), "artikel dari", url[:90])
    return out


def media_score(m):
    low = m.lower()
    return next((v for k, v in MEDIA_TIER.items() if k in low), 8)


def main():
    pats = load_emiten()
    raw = []
    for url, qa, qc in queries():
        raw += fetch(url, qanon=qa, qcorp=qc); time.sleep(1)
    for f in FEEDS:
        raw += fetch(f, default_media=f.split("/")[2].replace("www.", "")); time.sleep(1)
    print(len(raw), "artikel mentah diambil")

    old = {}
    if OUT.exists():
        old = {s["id"]: s for s in json.load(open(OUT, encoding="utf-8"))}
    old = {k: v for k, v in old.items() if "uma" in v}
    for r in raw:
        text = r["text"]
        anon, corp, st = hits(text, ANON), hits(text, CORP), stance_of(text)
        if r.get("qanon") and r["qanon"] not in anon:
            anon.append(r["qanon"])
        if r.get("qcorp") and r["qcorp"] != "uma" and r["qcorp"] not in corp:
            corp.append(r["qcorp"])
        uma = r.get("qcorp") == "uma" or bool(RE_UMA.search(text))
        if not (anon or corp or uma):
            continue
        tick = find_tickers(text, pats)
        sid = hashlib.sha1((r["title"] + r["media"]).encode()).hexdigest()[:12]
        old[sid] = dict(id=sid, title=r["title"], url=r["url"], media=r["media"], published=r["published"],
                        tickers=tick, uma=uma, anon=anon, corp=corp, stance=st, value_bn=idr_bn(text),
                        schedule=bool(RE_SCHED.search(text)), party=bool(RE_PARTY.search(r["text"])),
                        snippet=text[:300])
    cut = (NOW - dt.timedelta(days=365)).isoformat()
    items = [s for s in old.values() if s["published"] >= cut]
    score_all(items)
    items.sort(key=lambda s: s["published"], reverse=True)
    outcomes = list(csv.DictReader(open(ROOT / "data/outcomes.csv", encoding="utf-8")))
    for s in items:
        s["outcome"] = None
        for o in sorted(outcomes, key=lambda o: o["t0"]):
            if o["ticker"] in s["tickers"] and s["published"][:10] <= o["t0"] <= (
                    dt.date.fromisoformat(s["published"][:10]) + dt.timedelta(days=60)).isoformat():
                lead = (dt.date.fromisoformat(o["t0"]) - dt.date.fromisoformat(s["published"][:10])).days
                s["outcome"] = dict(status=o["status"], t0=o["t0"], lead_days=lead)
                break
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(items, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"updated": NOW.isoformat(), "count": len(items)}, open(OUT.parent / "meta.json", "w"))
    print(len(items), "sinyal tersimpan")


def score_all(items):
    P = lambda s: dt.datetime.fromisoformat(s["published"])

    def related(o, s):
        return bool(set(o["corp"]) & set(s["corp"])) or bool(o["anon"] and s["anon"])

    for s in items:
        win7 = {o["media"].lower() for o in items if set(o["tickers"]) & set(s["tickers"])
                and related(o, s) and abs((P(o) - P(s)).days) <= 7}
        later = sorted((o for o in items if set(o["tickers"]) & set(s["tickers"]) and o["stance"]
                        and 0 <= (P(o) - P(s)).total_seconds() <= 3 * 86400), key=P)
        resp = s["stance"] or (later[0]["stance"] if later else None)
        s["corroboration"] = len(win7)
        s["response"] = resp
        v = media_score(s["media"]) * 0.75
        v += min(len(s["anon"]), 3) * 10
        v += 35 if s.get("uma") else 0
        v += 10 if s["party"] else 0
        v += 10 if s["value_bn"] >= 1000 else 6 if s["value_bn"] >= 100 else 3 if s["value_bn"] > 0 else 0
        v += 5 if s["schedule"] else 0
        v += 10 if len(win7) >= 3 else 5 if len(win7) == 2 else 0
        v += {"terkonfirmasi": 10, "tanpa komentar": 5, "menunggu jawaban": 3, "membantah": -10}.get(resp, 0)
        if not s["anon"] and not s.get("uma"):
            v = min(v, 35)
        s["score"] = int(max(0, min(100, round(v))))


if __name__ == "__main__":
    main()
