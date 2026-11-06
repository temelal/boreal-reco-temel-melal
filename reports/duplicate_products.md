# duplicate-product investigation

i checked all 98 catalogue records, not just the baguette pair. normalising case, accents, punctuation and spaces gives 0 repeated item-name groups and 0 repeated english-name groups. there is no exact normalized-name duplicate. baguette and rustic baguette are a possible alias pair because they name the same bread family, but the rustic modifier and prices describe possible variants. no barcode is supplied, so exact stock-item identity is not verified.

## the pair and its buying profiles

| product | price | baskets | support |
| --- | --- | --- | --- |
| baguette | $2.99 | 69,400 | 6.9400% |
| rustic baguette | $3.99 | 42,219 | 4.2219% |

both labels occur together in 3,009 baskets. co-occurrence alone does not establish either duplication or separate product identity. i also compare their seasonal support and their links with raclette cheese and fondue broth, using the same underlying baskets:

| product | summer support | winter support | raclette confidence | raclette lift | fondue confidence | fondue lift |
| --- | --- | --- | --- | --- | --- | --- |
| baguette | 6.961% | 6.933% | 6.82% | 0.995 | 4.71% | 0.975 |
| rustic baguette | 2.163% | 6.924% | 65.44% | 9.552 | 41.00% | 8.489 |

the different profiles matter for recommendations. a shared word in the product name is not enough to assume interchangeable buying behaviour.

## a measured merge test

i made a separate 97-feature representation. the combined column is true when either baguette label is present, including when both appear. its count is 108,610, or 10.861% support. adding the separate counts would give 111,619 and double-count 3,009 baskets. all 1,000,000 baskets remain, while true matrix entries change from 8,379,837 to 8,376,828.

i re-ran apriori at support 0.005, confidence 0.2, low_memory=true and no maximum itemset length. retained rules have one consequent and lift above one.

| representation | itemsets | raw rules | retained rules | coverage | time seconds | peak mib |
| --- | --- | --- | --- | --- | --- | --- |
| original 98 products | 7,106 | 28,433 | 11,059 | 58/98 (59.18%) | 25.664 | 398.250 |
| merged 97 features | 7,142 | 28,482 | 11,094 | 58/97 (59.79%) | 25.652 | 441.344 |

the alternate coverage uses 97 features, including a family, while the original uses 98 catalogue entries. these percentages describe different units and cannot by themselves show a quality gain. here are the directly calculated rule metrics before and after merging:

| representation | antecedent | consequent | support | confidence | lift | passes confidence |
| --- | --- | --- | --- | --- | --- | --- |
| raw regular | baguette | raclette cheese | 0.4733% | 6.82% | 0.995 | no |
| raw regular | baguette | fondue broth | 0.3267% | 4.71% | 0.975 | no |
| raw rustic | rustic baguette | raclette cheese | 2.7627% | 65.44% | 9.552 | yes |
| raw rustic | rustic baguette | fondue broth | 1.7309% | 41.00% | 8.489 | yes |
| merged family | baguette family | raclette cheese | 3.0420% | 28.01% | 4.088 | yes |
| merged family | baguette family | fondue broth | 1.9402% | 17.86% | 3.699 | no |

the merged antecedent includes more baskets than the rustic variant. this changes conditional probabilities and loses a specific recommendation at the 20% confidence threshold. the comparison shows a real cost of treating the two profiles as one.

## final decision

i keep the two catalogue records separate. the full-name scan gives no exact duplicate, the prices and profiles differ, and the merge changes useful rules. the original 98-product model keeps this information and the separate sale prices. the 97-feature result is a sensitivity analysis, not a replacement application model.

this is an evidence-based negative finding: the supplied data does not verify a same-stock-item duplicate. a permanent merge would need the shop's stock identifiers. the audit records the pair, the normalization option, its measured effect and the reason for the final choice.
