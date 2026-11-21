#!/usr/bin/env python3
"""Fetch every `Routed` event from the StoaRouter on Robinhood Chain (4663)
via the public RPC, decode it, and write data/routed-robinhood.json.

Data source: eth_getLogs on https://rpc.mainnet.chain.robinhood.com
Event: Routed(address indexed sender, address indexed to, address indexed referrer,
              address tokenIn, address tokenOut, uint256 amountIn, uint256 amountOut,
              address mid, address venue1, address venue2)
topic0 = keccak256("Routed(address,address,address,address,address,uint256,uint256,address,address,address)")
       = 0x2bbce25631e8fa58085b7ea5929726c3acdf2df8d6b1f099eb32fb7425a4f6da

Usage: python3 scripts/fetch-routed.py [--from-block N] [--to-block N]
Writes: data/routed-robinhood.json (list of decoded swaps, oldest first)
"""
import argparse, json, os, sys, time, urllib.request

RPC = "https://rpc.mainnet.chain.robinhood.com"
ROUTER = "0x2F2804fad735a38015650f32f95Ad5E08D6B3eE5"
TOPIC0 = "0x2bbce25631e8fa58085b7ea5929726c3acdf2df8d6b1f099eb32fb7425a4f6da"
CHUNK = 100_000  # blocks per eth_getLogs call (verified working on this RPC)
UA = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data", "routed-robinhood.json")


def rpc(method, params, tries=4):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(RPC, data=body, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
            if "error" in d:
                raise RuntimeError(d["error"])
            return d["result"]
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def block_ts(n):
    b = rpc("eth_getBlockByNumber", [hex(n), False])
    return int(b["timestamp"], 16)


def find_block_at(ts_target):
    """Binary-search the first block with timestamp >= ts_target."""
    lo, hi = 0, int(rpc("eth_blockNumber", []), 16)
    while lo < hi:
        mid = (lo + hi) // 2
        if block_ts(mid) < ts_target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def word(data, i):
    return "0x" + data[2 + i * 64: 2 + (i + 1) * 64]


def addr_of(w):
    return "0x" + w[-40:]


def decode(log):
    t = log["topics"]
    d = log["data"]
    return {
        "blockNumber": int(log["blockNumber"], 16),
        "txHash": log["transactionHash"],
        "logIndex": int(log["logIndex"], 16),
        "sender": addr_of(t[1]).lower(),
        "to": addr_of(t[2]).lower(),
        "referrer": addr_of(t[3]).lower(),
        "tokenIn": addr_of(word(d, 0)).lower(),
        "tokenOut": addr_of(word(d, 1)).lower(),
        "amountIn": str(int(word(d, 2), 16)),
        "amountOut": str(int(word(d, 3), 16)),
        "mid": addr_of(word(d, 4)).lower(),
        "venue1": addr_of(word(d, 5)).lower(),
        "venue2": addr_of(word(d, 6)).lower(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-block", type=int, default=None)
    ap.add_argument("--to-block", type=int, default=None)
    args = ap.parse_args()

    latest = int(rpc("eth_blockNumber", []), 16)
    to_block = args.to_block or latest
    if args.from_block is not None:
        from_block = args.from_block
    else:
        # First Stoa swap on Robinhood was 2026-11-14; start 2026-11-11 to be safe.
        from_block = find_block_at(1794345600)
        print(f"start block for 2026-11-11: {from_block} (ts {block_ts(from_block)})")
    print(f"scanning blocks {from_block}..{to_block} (latest {latest})")

    swaps, seen_blocks = [], {}
    b = from_block
    while b <= to_block:
        e = min(b + CHUNK - 1, to_block)
        logs = rpc("eth_getLogs", [{
            "address": ROUTER, "topics": [TOPIC0],
            "fromBlock": hex(b), "toBlock": hex(e)}])
        for log in logs:
            swaps.append(decode(log))
        print(f"  {b}..{e}: {len(logs)} logs (total {len(swaps)})", flush=True)
        b = e + 1

    # Attach block timestamps (one RPC call per distinct block).
    for s in swaps:
        bn = s["blockNumber"]
        if bn not in seen_blocks:
            seen_blocks[bn] = block_ts(bn)
        s["timestamp"] = seen_blocks[bn]
    swaps.sort(key=lambda s: (s["blockNumber"], s["logIndex"]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"router": ROUTER, "chainId": 4663,
                   "fromBlock": from_block, "toBlock": to_block,
                   "fetchedAt": int(time.time()), "count": len(swaps),
                   "swaps": swaps}, f, indent=1)
    print(f"WROTE {OUT}: {len(swaps)} swaps")


if __name__ == "__main__":
    main()
