import csv
import importlib.util
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

from streamlit.testing.v1 import AppTest


project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project / "app"))
specification = importlib.util.spec_from_file_location(
    "boreal_recommendation_add_engine", project / "app" / "recommender.py"
)
engine = importlib.util.module_from_spec(specification)
specification.loader.exec_module(engine)


class RecommendationAddTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (project / "data" / "products.csv").open(encoding="utf-8-sig", newline="") as stream:
            cls.products = {row["Item"]: row for row in csv.DictReader(stream)}
        cls.rules = json.loads((project / "models" / "rules.json").read_text(encoding="utf-8"))
        cls.metadata = json.loads((project / "models" / "metadata.json").read_text(encoding="utf-8"))

    def setUp(self):
        self.app = AppTest.from_file(project / "app" / "streamlit_app.py", default_timeout=30)
        self.run_app()

    def run_app(self):
        self.app.run(timeout=30)
        self.assertEqual([element.message for element in self.app.exception], [])

    def metric(self, label):
        return next(element.value for element in self.app.metric if element.label == label)

    def search(self, item):
        self.app.text_input[0].set_value(self.products[item]["Item_EN"].lower())
        self.run_app()

    def click(self, key):
        self.app.button(key=key).click()
        self.run_app()

    def add_from_catalogue(self, item):
        self.search(item)
        self.click(f"add_{item}")

    def basket(self):
        return list(self.app.session_state["basket"])

    def right_targets(self):
        return [
            element.key.split("_", 1)[1]
            for element in self.app.button
            if element.key and element.key.startswith(("recommend_", "popular_"))
        ]

    def assert_basket(self, items, total):
        actual = self.basket()
        self.assertEqual(actual, items)
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(self.metric("basket total"), total)
        calculated = sum((Decimal(self.products[item]["Price"]) for item in actual), Decimal("0"))
        self.assertEqual(self.metric("basket total"), f"${calculated:.2f}")
        targets = self.right_targets()
        self.assertLessEqual(len(targets), 5)
        self.assertEqual(len(targets), len(set(targets)))
        self.assertFalse(set(items) & set(targets))

    def assert_catalogue_selected(self, item):
        self.search(item)
        button = self.app.button(key=f"add_{item}")
        self.assertTrue(button.disabled)
        self.assertEqual(button.label, "added")

    def assert_rule_view(self):
        expected = engine.recommend(self.basket(), self.rules)
        self.assertTrue(expected)
        self.assertEqual(self.right_targets(), [row["item"] for row in expected])
        self.assertFalse(any(element.key and element.key.startswith("popular_") for element in self.app.button))
        lifts = [float(row["lift"]) for row in expected]
        self.assertEqual(lifts, sorted(lifts, reverse=True))
        shown = next(element for element in self.app.expander if element.label == "rules that fired").dataframe[0].value
        expected_rows = [
            {
                "basket contains": ", ".join(
                    self.products[item]["Item_EN"].lower() for item in sorted(row["antecedents"])
                ),
                "suggested product": self.products[row["item"]]["Item_EN"].lower(),
                "support": f"{float(row['support']):.3%}",
                "confidence": f"{float(row['confidence']):.2%}",
                "lift": round(float(row["lift"]), 3),
            }
            for row in expected
        ]
        self.assertEqual(shown.to_dict("records"), expected_rows)
        metric_lines = [element.value for element in self.app.caption if element.value.startswith("support ")]
        self.assertEqual(
            metric_lines,
            [
                f"support {float(row['support']):.2%} · confidence {float(row['confidence']):.1%} · lift {float(row['lift']):.2f}"
                for row in expected
            ],
        )

    def assert_fallback_view(self):
        self.assertEqual(engine.recommend(self.basket(), self.rules), [])
        expected = engine.fallback(self.basket(), self.metadata["popularity"])
        self.assertEqual(self.right_targets(), [row["item"] for row in expected])
        self.assertFalse(any(element.key and element.key.startswith("recommend_") for element in self.app.button))
        metric_lines = [element.value for element in self.app.caption if element.value.startswith("support ")]
        self.assertEqual(metric_lines, ["support n/a · confidence n/a · lift n/a · strength n/a"] * len(expected))
        evidence = next(element for element in self.app.expander if element.label == "rules that fired")
        self.assertIn("no rule fired", "\n".join(element.value for element in evidence.markdown))

    def test_empty_fallback_add_updates_basket_total_and_exclusions(self):
        item = "Sac réutilisable"
        self.assert_basket([], "$0.00")
        self.assert_fallback_view()
        self.click(f"popular_{item}")
        self.assert_basket([item], "$1.49")
        self.assertNotIn(item, self.right_targets())
        self.assert_catalogue_selected(item)
        self.assert_fallback_view()
        self.run_app()
        self.assert_basket([item], "$1.49")
        self.assert_fallback_view()

    def test_rule_add_updates_order_evidence_and_can_be_removed(self):
        charcoal = "Charbon de bois"
        steak = "Steak de boeuf"
        self.add_from_catalogue(charcoal)
        self.assert_basket([charcoal], "$11.99")
        self.assert_rule_view()
        self.assertEqual(self.right_targets()[0], steak)
        self.click(f"recommend_{steak}")
        self.assert_basket([charcoal, steak], "$30.98")
        self.assertNotIn(steak, self.right_targets())
        self.assert_rule_view()
        self.assert_catalogue_selected(steak)
        self.run_app()
        self.assert_basket([charcoal, steak], "$30.98")
        self.assert_rule_view()
        self.click(f"remove_{steak}")
        self.assert_basket([charcoal], "$11.99")
        self.assert_rule_view()
        self.assertIn(steak, self.right_targets())
        self.assertFalse(self.app.button(key=f"recommend_{steak}").disabled)
        self.assertFalse(self.app.button(key=f"add_{steak}").disabled)

    def test_rare_product_fallback_add_preserves_warning_and_clears(self):
        rare = "Foie gras"
        popular = "Sac réutilisable"
        self.add_from_catalogue(rare)
        self.assert_basket([rare], "$44.99")
        warnings = "\n".join(element.value for element in self.app.warning)
        self.assertIn("756", warnings)
        self.assertIn("no saved rule can contain it", warnings)
        self.assert_fallback_view()
        self.click(f"popular_{popular}")
        self.assert_basket([rare, popular], "$46.48")
        self.assertNotIn(rare, self.right_targets())
        self.assertNotIn(popular, self.right_targets())
        self.assert_fallback_view()
        self.assert_catalogue_selected(popular)
        self.run_app()
        self.assert_basket([rare, popular], "$46.48")
        self.assertIn("no saved rule can contain it", "\n".join(element.value for element in self.app.warning))
        next(element for element in self.app.button if element.label == "clear basket").click()
        self.run_app()
        self.assert_basket([], "$0.00")
        self.assert_fallback_view()
        self.assertIn(popular, self.right_targets())


if __name__ == "__main__":
    unittest.main()
