import importlib.util
import json
import unittest
from collections import defaultdict
from pathlib import Path


root = Path(__file__).resolve().parents[1]
specification = importlib.util.spec_from_file_location("recommender", root / "app/recommender.py")
engine = importlib.util.module_from_spec(specification)
specification.loader.exec_module(engine)


class RecommendationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = json.loads((root / "models/rules.json").read_text(encoding="utf-8"))
        cls.metadata = json.loads((root / "models/metadata.json").read_text(encoding="utf-8"))
        cls.popularity = cls.metadata["popularity"]
        cls.rare = min(cls.metadata["item_supports"], key=cls.metadata["item_supports"].get)

    def test_empty_basket(self):
        self.assertEqual(engine.recommend([], self.rules), [])
        result = engine.fallback([], self.popularity)
        self.assertEqual(len(result), 5)
        self.assertEqual(len({row["item"] for row in result}), 5)
        self.assertEqual(result[0]["support"], max(row["support"] for row in self.popularity))

    def test_no_rule_fires(self):
        basket = [self.rare]
        self.assertEqual(engine.recommend(basket, self.rules), [])
        result = engine.fallback(basket, self.popularity)
        self.assertEqual(len(result), 5)
        self.assertNotIn(self.rare, {row["item"] for row in result})

    def test_items_already_in_basket(self):
        basket = self.rules[0]["antecedents"] + self.rules[0]["consequents"]
        self.assertFalse(set(basket) & {row["item"] for row in engine.recommend(basket, self.rules)})
        self.assertFalse(set(basket) & {row["item"] for row in engine.fallback(basket, self.popularity)})
        all_items = list(self.metadata["item_supports"])
        self.assertEqual(engine.recommend(all_items, self.rules), [])
        self.assertEqual(engine.fallback(all_items, self.popularity), [])

    def test_duplicate_suggestion_keeps_highest_lift(self):
        grouped = defaultdict(list)
        for rule in self.rules:
            grouped[rule["consequents"][0]].append(rule)
        item, candidates = next(
            (item, rows) for item, rows in grouped.items()
            if len({row["lift"] for row in rows}) > 1
        )
        low = min(candidates, key=lambda row: row["lift"])
        high = max(candidates, key=lambda row: row["lift"])
        basket = set(low["antecedents"] + high["antecedents"])
        matching = [row for row in candidates if set(row["antecedents"]) <= basket]
        self.assertGreater(len(matching), 1)
        result = [row for row in engine.recommend(basket, self.rules, limit=98) if row["item"] == item]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["lift"], max(row["lift"] for row in matching))

    def test_rare_product_has_no_rule(self):
        self.assertLess(self.metadata["item_supports"][self.rare], self.metadata["min_support"])
        used = {item for row in self.rules for item in row["antecedents"] + row["consequents"]}
        self.assertNotIn(self.rare, used)

    def test_multi_item_antecedent_needs_every_item(self):
        rule = next(row for row in self.rules if len(row["antecedents"]) > 1)
        self.assertEqual(engine.recommend(rule["antecedents"][:-1], [rule]), [])
        result = engine.recommend(rule["antecedents"], [rule])
        self.assertEqual([row["item"] for row in result], rule["consequents"])
        self.assertEqual(result[0]["antecedents"], rule["antecedents"])
        self.assertNotIn("item", rule)

    def test_descending_lift_and_limit(self):
        basket = ["Charbon de bois"]
        result = engine.recommend(basket, self.rules, limit=98)
        self.assertGreaterEqual(len(result), 5)
        lifts = [row["lift"] for row in result]
        self.assertEqual(lifts, sorted(lifts, reverse=True))
        self.assertEqual(engine.recommend(basket, self.rules, limit=3), result[:3])
        self.assertEqual(engine.recommend(basket, self.rules, limit=0), [])


if __name__ == "__main__":
    unittest.main()
