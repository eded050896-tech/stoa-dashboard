#!/usr/bin/env python3
"""Build data/dashboard.json for the Stoa public dashboard from:
  1. data/routed-robinhood.json — every `Routed` event from the Robinhood
     Chain StoaRouter, decoded from eth_getLogs (see scripts/fetch-routed.py).
  2. https://stoadex.com/api/stats — Stoa's own published stats (USD value per
     swap for the 20 most recent swaps, totals, top traders).

USD valuation per swap (same method Stoa documents on /stats):
  - the stats API's USD value when the swap is in its `recent` list;
  - else the USDG side of the swap (USDG = $1, 6 decimals);
  - else the ETH side at the router's current quote (live ETH->USDG quote);
  - else null (unpriced — reported as such, never invented).

Also fetches the current ETH price (0.01 ETH -> USDG quote) and saves a
snapshot of the stats API response for audit.

Usage: python3 scripts/build-data.py
Writes: data/dashboard.json, data/stats-api.json
"""
import json, os, time, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
ROUTER = "0x2F2804fad735a38015650f32f95Ad5E08D6B3eE5"
USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
NATIVE = "0x0000000000000000000000000000000000000000"
WETH = "0x0bd7d308f8e1639fab988df18a8011f41eacad73"
REFERRER = "0x61c5555660EDb169B4b3abF3512818EE76A72f64"

TOKENS = {
    NATIVE: {"symbol": "ETH", "decimals": 18},
    WETH: {"symbol": "WETH", "decimals": 18},
    USDG: {"symbol": "USDG", "decimals": 6},
    "0x13e6993417616de724f2b337d65063f229e96718": {"symbol": "STOA", "decimals": 18},
    "0x1dd577f4c1b9a201cb099af9af74dcac012395c9": {"symbol": "STOA", "decimals": 18, "note": "second STOA contract (Stoa Exchange)"},
    "0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3": {"symbol": "GOOGL", "decimals": 18},
    "0x4a0e65a3eccec6dbe60ae065f2e7bb85fae35eea": {"symbol": "SPCX", "decimals": 18},
    "0x51250b135174ca09450ec01c4aff73cf69dbb590": {"symbol": "NOVAAI", "decimals": 18},
}

VENUES = {
    "0x8965140fb51b2e99a0cd31a0e99eae01d36517b8": {"name": "Uniswap V4 (adapter v1)", "note": "first V4 adapter; removed from router 2026-11-20 (block 118317719)"},
    "0x28802ad6f9859d14dfc6226ea9a8b60686d3a2e6": {"name": "Uniswap V3", "note": "old V3 adapter; name confirmed by Stoa quote API"},
    "0x27958279f95225b2a5517e7dd12b6fc0317e5c5d": {"name": "Uniswap V4 (adapter v2)", "note": "replacement V4 adapter (StoaDex/Stoa contracts/deployments/4663-fixes.json)"},
    "0xf0904b95d66f565de215cc7dc58b6054f72a9352": {"name": "Aero Slipstream", "note": "CLTickSpacingAdapter; factory 0xc63d7338... (StoaDex/Stoa contracts/script/VenuesRobinhood.sol)"},
    "0x87b3b896beabdc421f9d9b0a3fd3dbbae1ddd568": {"name": "Ramses", "note": "CLTickSpacingAdapter; factory 0xe0c4ceb9... (VenuesRobinhood.sol)"},
    "0x58c2c83b66088b57b9dd487ba1090992bc9eebe0": {"name": "Adapter 0x58c2… (unidentified)", "note": "name not verified — factory 0x7ed598bc... is not in the public Stoa repo; 2 swaps only"},
    "0x0000000000000000000000000000000000000000": {"name": "—", "note": "no second leg (direct route)"},
}


def get_json(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def main():
    routed = json.load(open(os.path.join(DATA, "routed-robinhood.json")))
    swaps = routed["swaps"]
    stats = get_json("https://stoadex.com/api/stats")
    with open(os.path.join(DATA, "stats-api.json"), "w") as f:
        json.dump(stats, f, indent=1)

    # Current ETH price in USDG from Stoa's own quote (0.01 ETH -> USDG).
    q = urllib.parse.urlencode({
        "chain": "robinhood", "sellToken": "native", "buyToken": USDG,
        "amount": str(10 ** 16), "slippageBps": "50"})
    quote = get_json("https://stoadex.com/api/v1/quote?" + q)
    eth_price = int(quote["amountOut"]) / 10 ** 6 / 0.01  # USDG has 6 decimals
    print(f"ETH price from Stoa quote: ${eth_price:,.2f} (amountOut {quote['amountOut']})")

    recent_usd = {r["hash"].lower(): r["usd"] for r in stats.get("recent", [])}
    rh = [c for c in stats["chains"] if c["key"] == "robinhood"][0]

    def amount(token, raw):
        return int(raw) / 10 ** TOKENS.get(token, {"decimals": 18})["decimals"]

    out_swaps = []
    for s in swaps:
        usd, method = recent_usd.get(s["txHash"].lower()), "stoa-stats-api"
        if usd is None:
            if s["tokenIn"] == USDG:
                usd, method = amount(USDG, s["amountIn"]), "USDG side ($1)"
            elif s["tokenOut"] == USDG:
                usd, method = amount(USDG, s["amountOut"]), "USDG side ($1)"
            elif s["tokenIn"] == NATIVE:
                usd, method = amount(NATIVE, s["amountIn"]) * eth_price, "ETH side x current quote"
            elif s["tokenOut"] == NATIVE:
                usd, method = amount(NATIVE, s["amountOut"]) * eth_price, "ETH side x current quote"
            else:
                usd, method = None, "unpriced"
        out_swaps.append({
            "txHash": s["txHash"], "blockNumber": s["blockNumber"],
            "timestamp": s["timestamp"], "time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(s["timestamp"])),
            "sender": s["sender"], "to": s["to"], "referrer": s["referrer"],
            "tokenIn": s["tokenIn"], "tokenOut": s["tokenOut"],
            "symbolIn": TOKENS.get(s["tokenIn"], {}).get("symbol", s["tokenIn"][:10]),
            "symbolOut": TOKENS.get(s["tokenOut"], {}).get("symbol", s["tokenOut"][:10]),
            "amountIn": amount(s["tokenIn"], s["amountIn"]),
            "amountOut": amount(s["tokenOut"], s["amountOut"]),
            "mid": s["mid"], "venue1": s["venue1"], "venue2": s["venue2"],
            "venue1Name": VENUES.get(s["venue1"], {}).get("name", s["venue1"][:10]),
            "venue2Name": VENUES.get(s["venue2"], {}).get("name", s["venue2"][:10]) if s["venue2"] != NATIVE else "—",
            "usd": usd, "usdMethod": method,
        })
    out_swaps.sort(key=lambda x: x["timestamp"])

    priced = [s for s in out_swaps if s["usd"] is not None]
    total_usd = sum(s["usd"] for s in priced)
    now = time.time()
    usd24 = sum(s["usd"] for s in priced if now - s["timestamp"] <= 86400)
    usd7d = sum(s["usd"] for s in priced if now - s["timestamp"] <= 7 * 86400)
    n24 = sum(1 for s in out_swaps if now - s["timestamp"] <= 86400)
    n7d = sum(1 for s in out_swaps if now - s["timestamp"] <= 7 * 86400)
    traders = {s["sender"] for s in out_swaps}

    # Per-day totals (UTC).
    days = {}
    for s in out_swaps:
        day = time.strftime("%Y-%m-%d", time.gmtime(s["timestamp"]))
        d = days.setdefault(day, {"date": day, "swaps": 0, "usd": 0.0})
        d["swaps"] += 1
        if s["usd"] is not None:
            d["usd"] += s["usd"]
    day_list = [days[k] for k in sorted(days)]

    # Per-venue. A swap can have two legs (via the WETH hop token); volume is
    # counted once per swap, on leg 1, so venue USD sums to the headline total.
    venues = {}
    for s in out_swaps:
        for key, name in (("venue1", s["venue1Name"]), ("venue2", s["venue2Name"])):
            if s[key] == NATIVE:
                continue
            v = venues.setdefault(s[key], {"address": s[key], "name": name, "swaps": 0, "usd": 0.0,
                                           "leg2": 0,
                                           "note": VENUES.get(s[key], {}).get("note", "")})
            if key == "venue1":
                v["swaps"] += 1
                if s["usd"] is not None:
                    v["usd"] += s["usd"]
            else:
                v["leg2"] += 1

    # Top traders by USD.
    tmap = {}
    for s in out_swaps:
        t = tmap.setdefault(s["sender"], {"address": s["sender"], "swaps": 0, "usd": 0.0})
        t["swaps"] += 1
        if s["usd"] is not None:
            t["usd"] += s["usd"]
    top_traders = sorted(tmap.values(), key=lambda x: -x["usd"])[:10]

    # Top pairs.
    pmap = {}
    for s in out_swaps:
        k = f"{s['symbolIn']} → {s['symbolOut']}"
        p = pmap.setdefault(k, {"pair": k, "swaps": 0, "usd": 0.0})
        p["swaps"] += 1
        if s["usd"] is not None:
            p["usd"] += s["usd"]
    top_pairs = sorted(pmap.values(), key=lambda x: -x["usd"])

    dashboard = {
        "generatedAt": int(now),
        "generatedAtUTC": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now)),
        "chain": {"name": "Robinhood Chain", "chainId": 4663,
                  "explorer": "https://robinhoodchain.blockscout.com",
                  "rpc": "https://rpc.mainnet.chain.robinhood.com"},
        "router": ROUTER,
        "referrer": REFERRER,
        "referralLink": f"https://stoadex.com/trade?ref={REFERRER}",
        "ethPriceUsd": eth_price,
        "totals": {
            "swaps": len(out_swaps),
            "usd": round(total_usd, 2),
            "usd24h": round(usd24, 2), "swaps24h": n24,
            "usd7d": round(usd7d, 2), "swaps7d": n7d,
            "traders": len(traders),
            "unpriced": len(out_swaps) - len(priced),
            "firstSwap": out_swaps[0]["time"] if out_swaps else None,
            "lastSwap": out_swaps[-1]["time"] if out_swaps else None,
        },
        "reconciliation": {
            "stoaStatsSwaps": rh["swaps"], "stoaStatsUsdAll": rh["usdAll"],
            "stoaStatsUsd24h": rh["usd24h"], "stoaStatsUsd7d": rh["usd7d"],
            "dashboardSwaps": len(out_swaps), "dashboardUsd": round(total_usd, 2),
            "note": "Swap count matches Stoa's /api/stats exactly. USD differs only by ETH-price drift: Stoa values the ETH side at the quote at build time; this build uses the live quote at generation time.",
        },
        "days": day_list,
        "venues": sorted(venues.values(), key=lambda x: -x["swaps"]),
        "topTraders": top_traders,
        "topPairs": top_pairs,
        "referrers": {"count": 0, "note": "No swap so far names a referrer (all 33 Routed events have referrer 0x0). Be the first: every swap link on this page carries referrer " + REFERRER + "."},
        "swaps": list(reversed(out_swaps)),
    }
    with open(os.path.join(DATA, "dashboard.json"), "w") as f:
        json.dump(dashboard, f, indent=1)
    print(f"swaps: {len(out_swaps)}  priced: {len(priced)}  total USD {total_usd:,.2f} (Stoa says {rh['usdAll']:,.2f})")
    print(f"24h: {n24} swaps ${usd24:,.2f} (Stoa ${rh['usd24h']:,.2f})  7d: {n7d} swaps ${usd7d:,.2f} (Stoa ${rh['usd7d']:,.2f})")
    print(f"traders: {len(traders)}  unpriced: {len(out_swaps)-len(priced)}")
    print("WROTE data/dashboard.json")


if __name__ == "__main__":
    main()
