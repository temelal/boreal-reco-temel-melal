import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
from mlxtend.frequent_patterns import apriori, association_rules


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--basket", required=True)
    parser.add_argument("--items", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-support", type=float, required=True)
    parser.add_argument("--min-confidence", type=float, default=0.2)
    parser.add_argument("--low-memory", action="store_true")
    parser.add_argument("--extra-memory-mib", type=int, default=0)
    args = parser.parse_args()
    items = json.loads(Path(args.items).read_text(encoding="utf-8"))
    values = np.load(args.basket, mmap_mode="r")
    basket = pd.DataFrame(values, columns=items, copy=False)
    process = psutil.Process()
    result = {
        "min_support": args.min_support,
        "min_confidence": args.min_confidence,
        "low_memory": args.low_memory,
        "max_len": None,
        "basket_count": len(basket),
        "extra_memory_mib": args.extra_memory_mib,
        "baseline_memory_mib": process.memory_info().rss / 1024**2,
    }
    if args.extra_memory_mib:
        limit = process.memory_info().vms + args.extra_memory_mib * 1024**2
        resource.setrlimit(resource.RLIMIT_AS, (limit, resource.RLIM_INFINITY))
    started = time.perf_counter()
    try:
        itemsets = apriori(
            basket,
            min_support=args.min_support,
            use_colnames=True,
            low_memory=args.low_memory,
        )
        result["mining_seconds"] = time.perf_counter() - started
        rules_started = time.perf_counter()
        if len(itemsets):
            rules = association_rules(
                itemsets,
                num_itemsets=len(basket),
                metric="confidence",
                min_threshold=args.min_confidence,
            )
        else:
            rules = pd.DataFrame()
        result["rule_seconds"] = time.perf_counter() - rules_started
        result["n_itemsets"] = len(itemsets)
        result["n_rules"] = len(rules)
        result["outcome"] = "completed"
        result["itemsets"] = [
            {"items": sorted(row.itemsets), "support": float(row.support)}
            for row in itemsets.itertuples(index=False)
        ]
        result["rules"] = [
            {
                "antecedents": sorted(row["antecedents"]),
                "consequents": sorted(row["consequents"]),
                "support": float(row["support"]),
                "confidence": float(row["confidence"]),
                "lift": float(row["lift"]),
                "antecedent_support": float(row["antecedent support"]),
                "consequent_support": float(row["consequent support"]),
            }
            for row in rules.to_dict("records")
        ]
    except MemoryError as error:
        result["outcome"] = "memoryerror"
        result["error"] = str(error)
        result["n_itemsets"] = None
        result["n_rules"] = None
    result["elapsed_seconds"] = time.perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result["peak_memory_mib"] = peak / (1024**2 if sys.platform == "darwin" else 1024)
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in result.items() if k not in {"rules", "itemsets"}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
