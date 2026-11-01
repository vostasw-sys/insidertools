"""Anomali harga/volume: z-score volume 5 hari terakhir dan return abnormal vs IHSG.
Menambah poin skor bila ada lonjakan tidak biasa pada emiten yang punya sinyal berita."""
import json, datetime as dt
from pathlib import Path
import yfinance as yf

P = Path(__file__).resolve().parent.parent / "docs/data/signals.json"
sig = json.load(open(P, encoding="utf-8"))
cut = (dt.date.today() - dt.timedelta(days=14)).isoformat()
tick = sorted({t for s in sig if s["published"][:10] >= cut and (s["anon"] or s.get("uma"))
               for t in s["tickers"]})[:60]
res = {}
for t in tick:
    try:
        d = yf.download([t + ".JK", "^JKSE"], period="6mo", auto_adjust=True, progress=False)
        c, v = d["Close"].dropna(), d["Volume"][t + ".JK"].dropna()
        base = v.iloc[-65:-5]
        z = (v.iloc[-5:].mean() - base.mean()) / (base.std() or 1)
        r = c.iloc[-1] / c.iloc[-6] - 1
        res[t] = dict(vol_z=round(float(z), 2), abn5=round(float(r[t + ".JK"] - r["^JKSE"]) * 100, 2),
                      last=str(c.index[-1].date()))
    except Exception as e:
        print("lewati", t, e)
for s in sig:
    a = [res[t] for t in s["tickers"] if t in res]
    s["anomali"] = max(a, key=lambda x: x["vol_z"]) if a else None
    if s["anomali"] and (s["anomali"]["vol_z"] >= 2.5 or abs(s["anomali"]["abn5"]) >= 5):
        s["score"] = min(100, s["score"] + 15)
json.dump(sig, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(res), "emiten dicek anomali harga")
