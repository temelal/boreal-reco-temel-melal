import json
import unittest
from pathlib import Path

import pandas as pd


root = Path(__file__).resolve().parents[1]


class DuplicateProductTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = json.loads((root / "reports/analysis_results.json").read_text(encoding="utf-8"))
        cls.audit = cls.analysis["duplicate_audit"]
        cls.metadata = json.loads((root / "models/metadata.json").read_text(encoding="utf-8"))
        cls.catalogue = pd.read_csv(root / "data/products.csv")
        cls.baskets = {"Baguette": set(), "Pain baguette rustique": set()}
        cls.rows = 0
        cls.raw_items = set()
        for chunk in pd.read_csv(
            root / "data/transactions.zip",
            usecols=["TransactionID", "Item"],
            dtype={"TransactionID": "int32", "Item": "string"},
            chunksize=500_000,
        ):
            cls.rows += len(chunk)
            cls.raw_items.update(chunk["Item"].unique())
            for item, basket_ids in cls.baskets.items():
                basket_ids.update(chunk.loc[chunk["Item"].eq(item), "TransactionID"].tolist())

    def test_set_union_and_presence_counts(self):
        first = self.baskets["Baguette"]
        second = self.baskets["Pain baguette rustique"]
        overlap = len(first & second)
        union = len(first | second)
        self.assertEqual((len(first), len(second), overlap, union), (69400, 42219, 3009, 108610))
        self.assertEqual(union, len(first) + len(second) - overlap)
        self.assertEqual(self.audit["overlap_baskets"], overlap)
        self.assertEqual(self.audit["union_baskets"], union)
        self.assertEqual(self.audit["naive_sum"], len(first) + len(second))
        self.assertEqual(self.audit["raw_presences"], self.rows)
        self.assertEqual(self.rows, 8379837)
        self.assertEqual(self.audit["merged_presences"], self.rows - overlap)
        self.assertEqual(self.audit["merged_presences"], 8376828)

    def test_original_catalogue_and_identity_uncertainty(self):
        catalogue_items = set(self.catalogue["Item"])
        self.assertEqual(len(self.catalogue), 98)
        self.assertEqual(catalogue_items, self.raw_items)
        self.assertTrue(set(self.baskets) <= catalogue_items)
        self.assertEqual(self.metadata["product_count"], 98)
        self.assertEqual(self.audit["raw_products"], 98)
        self.assertEqual(self.audit["merged_products"], 97)
        self.assertIs(self.audit["exact_identity_verified"], False)

    def test_alternate_mining_preserves_parameters(self):
        merged = self.analysis["merged_sensitivity"]
        self.assertEqual(merged["outcome"], "completed")
        self.assertEqual(merged["basket_count"], self.metadata["basket_count"])
        self.assertEqual(merged["product_count"], 97)
        self.assertEqual(merged["denominator"], 97)
        self.assertGreater(merged["n_rules"], 0)
        self.assertEqual(merged["min_support"], self.metadata["min_support"])
        self.assertEqual(merged["min_confidence"], self.metadata["min_confidence"])
        self.assertIs(merged["low_memory"], True)
        self.assertIsNone(merged["max_len"])
        comparisons = self.analysis["duplicate_rule_comparison"]
        threshold = self.metadata["min_confidence"]
        self.assertTrue(comparisons)
        for row in comparisons:
            self.assertEqual(row["passes_confidence"], row["confidence"] >= threshold)
        fondue = {
            row["representation"]: row
            for row in comparisons if row["consequent"] == "fondue broth"
        }
        self.assertGreater(fondue["raw rustic"]["confidence"], threshold)
        self.assertLess(fondue["merged family"]["confidence"], threshold)


if __name__ == "__main__":
    unittest.main()
