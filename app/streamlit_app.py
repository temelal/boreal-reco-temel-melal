import json
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

from recommender import fallback, recommend


st.set_page_config(page_title="boréal marché", page_icon="🛒", layout="wide")

base = Path(__file__).resolve().parents[1]
categories = {
    "Boissons": "drinks",
    "Boulangerie": "bakery",
    "Bébé": "baby",
    "Collations": "snacks",
    "Fromages": "cheese",
    "Fruits et légumes": "fruit and vegetables",
    "Maison": "household",
    "Poissons": "fish",
    "Produits laitiers": "dairy",
    "Spécialités": "specialities",
    "Surgelés": "frozen food",
    "Viandes": "meat",
    "Épicerie": "grocery",
}


@st.cache_data
def load_assets(product_stamp, rules_stamp, metadata_stamp):
    products = pd.read_csv(base / "data" / "products.csv")
    rules_path = base / "models" / "rules.json"
    metadata_path = base / "models" / "metadata.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8")) if rules_path.exists() else []
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    return products, rules, metadata


def search_key(value):
    return "".join(
        letter
        for letter in unicodedata.normalize("NFKD", str(value).casefold())
        if not unicodedata.combining(letter)
    )


def add_item(item):
    if item not in st.session_state.basket:
        st.session_state.basket.append(item)


def remove_item(item):
    st.session_state.basket = [value for value in st.session_state.basket if value != item]


def clear_basket():
    st.session_state.basket = []


asset_paths = [base / "data" / "products.csv", base / "models" / "rules.json", base / "models" / "metadata.json"]
products, saved_rules, metadata = load_assets(
    *(path.stat().st_mtime_ns if path.exists() else 0 for path in asset_paths)
)
catalogue = products.set_index("Item").to_dict("index")


def name(item):
    return str(catalogue.get(item, {}).get("Item_EN", item)).lower()


def category(item):
    raw = str(catalogue.get(item, {}).get("Category", ""))
    return categories.get(raw, raw.lower())


def details(item):
    return f"{category(item)} · ${float(catalogue[item]['Price']):.2f}"


def strength(lift):
    thresholds = metadata.get("strength_thresholds", {})
    if lift >= thresholds.get("very_strong", 4.0):
        return "very strong"
    if lift >= thresholds.get("strong", 2.0):
        return "strong"
    if lift >= thresholds.get("moderate", 1.2):
        return "moderate"
    return "weak"


if "basket" not in st.session_state:
    st.session_state.basket = []
st.session_state.basket = [item for item in st.session_state.basket if item in catalogue]
basket = st.session_state.basket
popularity = [row for row in metadata.get("popularity", []) if row.get("item") in catalogue]
item_supports = metadata.get("item_supports", {})
rules = [
    row for row in saved_rules
    if len(row.get("consequents", [])) == 1
    and row["consequents"][0] in catalogue
    and all(item in catalogue for item in row.get("antecedents", []))
]

st.title("boréal marché")
st.caption("a small basket recommender using the rules saved from our transaction data")
stat_columns = st.columns(3)
stat_columns[0].metric("baskets analysed", f"{metadata.get('basket_count', 0):,}")
stat_columns[1].metric("catalogue products", len(products))
stat_columns[2].metric("saved rules", len(rules))
if not metadata or not saved_rules:
    st.warning("the saved mining files are missing or empty. run the mining notebook before using recommendations.")
else:
    st.caption(
        f"mined on {str(metadata.get('mining_date', 'unknown')).lower()} · "
        f"minimum support {float(metadata.get('min_support', 0)):.2%} · "
        f"minimum confidence {float(metadata.get('min_confidence', 0)):.0%} · "
        f"product coverage {float(metadata.get('coverage', 0)):.1%}"
    )

catalogue_zone, basket_zone, recommendation_zone = st.columns([1.2, 1, 1.35], gap="large")

with catalogue_zone:
    st.subheader("catalogue")
    selected_category = st.selectbox("category", ["all categories"] + sorted(set(categories.values())))
    query = st.text_input("search by name", placeholder="english or french product name")
    visible = products.copy()
    if selected_category != "all categories":
        visible = visible[visible["Item"].map(category) == selected_category]
    if query.strip():
        token = search_key(query.strip())
        visible = visible[
            visible.apply(lambda row: token in search_key(f"{row['Item_EN']} {row['Item']}"), axis=1)
        ]
    st.caption(f"{len(visible)} of {len(products)} products")
    with st.container(height=610):
        if visible.empty:
            st.info("no product matches this search.")
        for row in visible.sort_values("Item_EN").to_dict("records"):
            item = row["Item"]
            description_column, button_column = st.columns([3, 1])
            with description_column:
                st.markdown(f"**{name(item)}**")
                st.caption(details(item))
                if item in item_supports:
                    st.caption(f"in {float(item_supports[item]):.2%} of baskets")
            with button_column:
                st.button(
                    "added" if item in basket else "add",
                    key=f"add_{item}",
                    disabled=item in basket,
                    on_click=add_item,
                    args=(item,),
                    width="stretch",
                )
            st.divider()

with basket_zone:
    st.subheader("your basket")
    st.caption(f"{len(basket)} different products · one of each")
    if not basket:
        st.info("your basket is empty. add a product from the catalogue to try a rule.")
    for item in basket:
        description_column, button_column = st.columns([2, 1])
        with description_column:
            st.markdown(f"**{name(item)}**")
            st.caption(details(item))
        with button_column:
            st.button("remove", key=f"remove_{item}", on_click=remove_item, args=(item,))
        support = item_supports.get(item)
        minimum = float(metadata.get("min_support", 0))
        if support is not None and float(support) < minimum:
            count = round(float(support) * int(metadata.get("basket_count", 0)))
            st.warning(
                f"{name(item)} appears in only {count:,} baskets ({float(support):.3%}). "
                f"this is below the {minimum:.2%} minimum support, so no saved rule can contain it."
            )
        st.divider()
    total = sum(float(catalogue[item]["Price"]) for item in basket)
    st.metric("basket total", f"${total:.2f}")
    st.button("clear basket", on_click=clear_basket, disabled=not basket, width="stretch")

with recommendation_zone:
    st.subheader("recommendations")
    suggestions = recommend(basket, rules)
    if suggestions:
        st.caption("up to 5 suggestions, ordered by highest lift. products already in the basket are excluded.")
        for suggestion in suggestions:
            item = suggestion["item"]
            st.markdown(f"**{name(item)}**")
            st.caption(f"{details(item)} · {strength(float(suggestion['lift']))}")
            triggers = ", ".join(name(value) for value in sorted(suggestion["antecedents"]))
            st.write(
                f"because your basket contains {triggers}, customers who buy these also buy "
                f"{name(item)} {float(suggestion['confidence']):.1%} of the time. "
                f"this is {float(suggestion['lift']):.2f}× more often than average."
            )
            st.caption(
                f"support {float(suggestion['support']):.2%} · "
                f"confidence {float(suggestion['confidence']):.1%} · "
                f"lift {float(suggestion['lift']):.2f}"
            )
            st.divider()
        with st.expander("rules that fired"):
            shown_rules = [
                {
                    "basket contains": ", ".join(name(item) for item in sorted(row["antecedents"])),
                    "suggested product": name(row["item"]),
                    "support": f"{float(row['support']):.3%}",
                    "confidence": f"{float(row['confidence']):.2%}",
                    "lift": round(float(row["lift"]), 3),
                }
                for row in suggestions
            ]
            st.dataframe(pd.DataFrame(shown_rules), hide_index=True, width="stretch")
            st.caption("these are the exact rules behind the suggestions above. when rules suggest the same product, only the highest lift is kept.")
    else:
        if not basket:
            st.info("no rule can fire with an empty basket. these are popular products to start with.")
        else:
            st.info("no saved rule matches this basket. here are popular products instead.")
        popular_suggestions = fallback(basket, popularity)
        if not popular_suggestions:
            st.write("no new popular product is available for this basket.")
        for suggestion in popular_suggestions:
            item = suggestion["item"]
            st.markdown(f"**{name(item)}**")
            st.caption(f"{details(item)} · popular product")
            st.write(f"popular fallback: no basket rule fired. in {float(suggestion.get('support', 0)):.1%} of all baskets.")
            st.caption("support n/a · confidence n/a · lift n/a · strength n/a")
            st.divider()
        with st.expander("rules that fired"):
            st.write("no rule fired. the suggestions use overall product popularity.")

with st.expander("popular products and saved rule details"):
    if popularity:
        popular_table = pd.DataFrame(
            [
                {
                    "product": name(row["item"]),
                    "baskets": int(row.get("count", 0)),
                    "share of baskets": f"{float(row.get('support', 0)):.2%}",
                }
                for row in popularity[:10]
            ]
        )
        st.dataframe(popular_table, hide_index=True, width="stretch")
    st.write(
        f"the saved rules can recommend {metadata.get('recommended_products', 0)} of {len(products)} products. "
        "coverage counts rule consequents; the popularity fallback is excluded."
    )
    thresholds = metadata.get("strength_thresholds", {})
    moderate = float(thresholds.get("moderate", 1.2))
    strong = float(thresholds.get("strong", 2.0))
    very_strong = float(thresholds.get("very_strong", 4.0))
    st.caption(
        f"strength labels: weak below {moderate:g}, moderate from {moderate:g}, "
        f"strong from {strong:g}, very strong from {very_strong:g}. all saved rules have lift above 1."
    )
    st.caption("these are purchase associations. they do not show that buying one product causes another purchase.")
