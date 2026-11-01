"""Event study sederhana (market-adjusted vs IHSG) untuk setiap baris di data/outcomes.csv."""
import csv, json, datetime as dt
from pathlib import Path
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
signals = json.load(open(ROOT / "docs/data/signals.json", encoding="utf-8"))
events = []


def car(px, a, b):
    """Return kumulatif saham dikurangi IHSG dari tanggal a ke b (harga penutupan terdekat)."""
    try:
        sub = px.loc[:pd.Timestamp(b)].iloc[-1], px.loc[:pd.Timestamp(a)].iloc[-1]
        r = sub[0] / sub[1] - 1
        return round(float(r.iloc[0] - r.iloc[1]) * 100, 2)
    except Exception:
        return None


for o in csv.DictReader(open(ROOT / "data/outcomes.csv", encoding="utf-8")):
    t0 = dt.date.fromisoformat(o["t0"])
    sig = [s for s in signals if o["ticker"] in s["tickers"]
           and 0 <= (t0 - dt.date.fromisoformat(s["published"][:10])).days <= 60]
    first = min((s["published"][:10] for s in sig), default=None)
    start = dt.date.fromisoformat(first) if first else t0
    px = yf.download([o["ticker"] + ".JK", "^JKSE"], start=start - dt.timedelta(days=10),
                     end=t0 + dt.timedelta(days=10), auto_adjust=True, progress=False)["Close"]
    px = px.dropna()
    events.append(dict(ticker=o["ticker"], t0=o["t0"], status=o["status"], first_signal=first,
                       lead_days=(t0 - start).days if first else None, n_signals=len(sig),
                       max_score=max((s["score"] for s in sig), default=None),
                       car_pre=car(px, start - dt.timedelta(days=1), t0 - dt.timedelta(days=1)) if len(px) else None,
                       car_event=car(px, t0 - dt.timedelta(days=1), t0 + dt.timedelta(days=1)) if len(px) else None))
json.dump(events, open(ROOT / "docs/data/events.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(events), "event dihitung")
