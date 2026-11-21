# Stoa Swaps · Robinhood Chain — Public Dashboard

A public dashboard of every swap routed through the Stoa router on Robinhood
Chain: volume, traders, and routes per venue. Built for the **Stoa build
bounty #3** ("Public dashboard", $50 USDG — https://stoadex.com/build#bounties).

- **Live page:** _(GitHub Pages URL goes here after publish — see "Publish" below)_
- **Data:** on-chain `Routed` events, fetched from the public RPC — no keys.
- **Referrer:** every swap link on the page carries
  `0x61c5555660EDb169B4b3abF3512818EE76A72f64` as referrer
  (`https://stoadex.com/trade?ref=0x61c5555660EDb169B4b3abF3512818EE76A72f64`).

## What it shows

- Total volume (USD), swap count, unique traders, 24h / 7d views
- Volume per day (UTC)
- Routes per venue — which venue filled each swap (leg 1 and leg 2)
- Top pairs, top traders, latest swaps (with Blockscout links)
- Swap links to Stoa with the referrer above (the page itself never sends swaps)

## Data sources & queries

| Data | Source | How |
|---|---|---|
| Swaps | Robinhood Chain public RPC `https://rpc.mainnet.chain.robinhood.com` | `eth_getLogs` on StoaRouter `0x2F2804fad735a38015650f32f95Ad5E08D6B3eE5`, topic0 `0x2bbce256…` (`Routed(address,address,address,address,address,uint256,uint256,address,address,address)`) — see `scripts/fetch-routed.py` |
| USD values | Stoa's own stats API `https://stoadex.com/api/stats` | The API's USD value for its 20 most recent swaps; otherwise the USDG side (USDG = $1), otherwise the ETH side at the live ETH→USDG quote from `GET /api/v1/quote`. Same method Stoa documents on stoadex.com/stats. |
| ETH price | Stoa quote API | `GET /api/v1/quote?chain=robinhood&sellToken=native&buyToken=<USDG>&amount=10000000000000000` |
| Token symbols/decimals | Stoa token list + on-chain `symbol()`/`decimals()` | `GET /api/v1/tokens?chain=robinhood`, verified on-chain for STOA / SPCX / GOOGL |
| Venue names | Stoa public repo + quote API | StoaDex/Stoa `contracts/script/VenuesRobinhood.sol`, `contracts/deployments/4663-*.json`, deploy scripts, and the quote API's `route.legs[].name` |

**Reconciliation (last build):** 33 swaps — exactly Stoa's `/api/stats` count.
USD total $685.29 vs Stoa's $685.29 (24h: 3 swaps / $4.99, exact). The
totals move together because both value the ETH side at the current quote.

**Venue identification (verified):**

| Venue address | Name | How verified |
|---|---|---|
| `0x8965140f…` | Uniswap V4 (adapter v1) | StoaDex/Stoa `V4AdapterV3Robinhood.sol` ("first V4 adapter"); removed from the router 2026-11-20 (block 118317719) |
| `0x28802ad6…` | Uniswap V3 | Stoa quote API returns `name: "Uniswap V3"` for this venue |
| `0x27958279…` | Uniswap V4 (adapter v2) | `contracts/deployments/4663-fixes.json` |
| `0xf0904b95…` | Aero Slipstream | CLTickSpacingAdapter; its `factory()` is `0xc63d7338…` = `AERO_CL_FACTORY` in `VenuesRobinhood.sol` |
| `0x87b3b896…` | Ramses | CLTickSpacingAdapter; its `factory()` is `0xe0c4ceb9…` = `RAMSES_CL_FACTORY` |
| `0x58c2c83b…` | _unidentified_ | 2 swaps only; its factory (`0x7ed598bc…`) is not in the public repo — labelled as unidentified, not guessed |

**Caveats (shown on the page too):** Stoa on Robinhood Chain is days old —
33 swaps, ~$685 total, including the team's own launch checks (Stoa says so
on its stats page). Two different STOA contracts exist on the chain; both are
named STOA on-chain. No swap so far names a referrer (all 33 `Routed`
events have referrer `0x0`).

## How to refresh the data

```bash
bash scripts/refresh.sh   # re-runs fetch-routed.py + build-data.py
```

This re-fetches all `Routed` events and rebuilds `data/dashboard.json`.
It only reads public endpoints; it costs nothing and signs nothing.

## Publish (GitHub Pages, free)

```bash
git init && git add . && git commit -m "Stoa Robinhood swaps dashboard"
# create a public repo on GitHub, then:
git remote add origin https://github.com/<you>/stoa-robinhood-dashboard.git
git push -u origin main
# Repo → Settings → Pages → Source: Deploy from a branch → main, /(root)
```

The page is a single static `index.html` + `data/dashboard.json` — no build
step. It tries to fetch `https://stoadex.com/api/stats` for fresh headline
totals, but Stoa's API sends no CORS headers, so browsers on another origin
cannot read it; the page then uses the bundled snapshot (regenerate with
`scripts/refresh.sh`).

## Submit the bounty

Open a new issue in **StoaDex/Stoa** with label `bounty`
(https://github.com/StoaDex/Stoa/issues/new?title=Bounty%3A%20&labels=bounty),
titled e.g. `Bounty: Public dashboard of Stoa swaps on Robinhood Chain`, with:

- the live dashboard URL (GitHub Pages)
- this repo URL (open source)
- how it uses Stoa's data (on-chain `Routed` events + `/api/stats` + `/api/v1/quote`)
- the referrer address and that every swap link carries it

Stoa checks each entry before paying; one bounty per person; no wash
trading. The dashboard never sends swaps itself.
