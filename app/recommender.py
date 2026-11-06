def recommend(basket, rules, limit=5):
    present = set(basket)
    candidates = []
    for rule in rules:
        antecedents = set(rule.get("antecedents", []))
        consequents = rule.get("consequents", [])
        if not antecedents or not antecedents.issubset(present):
            continue
        if len(consequents) != 1 or consequents[0] in present:
            continue
        if float(rule.get("lift", 0)) <= 1:
            continue
        candidates.append({**rule, "item": consequents[0]})
    candidates.sort(
        key=lambda row: (
            -float(row["lift"]),
            -float(row["confidence"]),
            -float(row["support"]),
            row["item"],
            tuple(sorted(row["antecedents"])),
        )
    )
    selected = []
    seen = set()
    for row in candidates:
        if row["item"] not in seen:
            selected.append(row)
            seen.add(row["item"])
        if len(selected) >= max(0, limit):
            break
    return selected if limit > 0 else []


def fallback(basket, popularity, limit=5):
    present = set(basket)
    ranked = sorted(
        popularity,
        key=lambda row: (
            -float(row.get("support", 0)),
            -int(row.get("count", 0)),
            row["item"],
        ),
    )
    selected = []
    seen = set()
    for row in ranked:
        item = row["item"]
        if item not in present and item not in seen:
            selected.append(dict(row))
            seen.add(item)
        if len(selected) >= max(0, limit):
            break
    return selected if limit > 0 else []
