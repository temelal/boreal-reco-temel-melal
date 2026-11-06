# apriori benchmark

these values come from the executed notebook and `analysis_results.json` in this folder. i used all 1,000,000 baskets and all 98 original catalogue products. no row sampling or maximum itemset length was used.

## preparation and environment

- system: darwin 27.2.0, arm64, python 3.12.14, 64 gib physical memory.
- load the full zip: 0.932 seconds; the typed long table occupies 87.926 mib.
- build the wide boolean table: 0.094 seconds, shape 1,000,000 by 98.
- array storage: 93.460 mib; dataframe storage including its index: 93.460 mib.

i factorize the transaction ids, map products to catalogue positions, allocate one boolean array and mark the observed basket-product positions. this directly creates the required wide format. it avoids an intermediate dummy table with one row for every raw line item.

each experiment runs in a new worker process and uses the same one-million-row matrix loaded from a temporary numpy file. time starts after this loading and covers apriori, association rule generation and conversion to python records. process startup, matrix creation, saving the input matrix and writing the result json are outside this timer. peak memory is the whole worker's high-water resident memory, including libraries, input data and temporary allocations. it is measured with resource.getrusage; bytes on macos and kib on linux are converted to mib. matrix storage and process peak are different measurements.

## the default allocation failure

at support 0.05, confidence 0.20 and low_memory=false, the result was `memoryerror` after 0.063 seconds. worker peak memory was 201.297 mib. the failed request was a 4.76 gib boolean array with shape 2556 by 2 by 1,000,000.

this was a controlled memory-error experiment. after loading its data and libraries, the worker was given 1,024 mib of extra virtual address-space headroom using an operating-system resource limit. the same headroom was used for the successful runs. it is an address-space limit, and the computer has 64 gib of physical memory. i did not wait for the whole machine to run out of ram.

the 93.46 mib basket array is not the main problem. default apriori evaluates many candidate combinations against all baskets in a large temporary allocation. low_memory=true processes candidates in smaller groups and avoids this request. it can cost more computation in return for lower temporary memory. i kept apriori itself and did not use another mining algorithm.

## four full-data runs

all runs use confidence 0.20, low_memory=true and no maximum itemset length. rules in this table are the raw confidence-qualified rules, before the final lift and singleton-consequent filters.

| min_support | itemsets | rules | time seconds | peak memory mib | outcome |
| --- | --- | --- | --- | --- | --- |
| 0.05 | 191 | 282 | 1.130 | 371.969 | completed |
| 0.02 | 658 | 3,159 | 3.036 | 405.766 | completed |
| 0.01 | 2,267 | 9,736 | 8.979 | 417.500 | completed |
| 0.005 | 7,106 | 28,433 | 25.664 | 398.250 | completed |

all four runs completed. lower support makes more combinations survive, so there is much more work and many more rules. these are measurements from one execution, not a speed guarantee. process peaks also depend on allocations and the operating system, so the measured peaks need not rise in a perfectly steady way.

## choice and coverage

retaining one-product consequents and lift above one gives:

| min_support | retained rules | recommendable products | coverage |
| --- | --- | --- | --- |
| 0.05 | 173 | 27 | 27.55% |
| 0.02 | 1,264 | 57 | 58.16% |
| 0.01 | 3,460 | 58 | 59.18% |
| 0.005 | 11,059 | 58 | 59.18% |

i selected support 0.005, confidence 0.2 and lift above one. this keeps 11,059 rules, including 10,705 multi-item antecedents, for the basket demonstration. coverage is 58/98, or 59.18%; it counts different products that can appear as a rule consequent. fallback products are excluded.

support 0.01 already reaches the same 58 products with 3,460 retained rules. choosing 0.005 adds more antecedent combinations, but no extra product coverage, and costs more time. for a small production catalogue i would consider 0.01 first and only keep the larger rule set if basket evaluation shows a useful benefit. i do not claim that more rules are automatically better.

the five very rare speciality products cannot survive even 0.005. for example foie gras appears in 756 baskets, or 0.0756%. no superset containing it can have higher support than that product alone. the application explains this and falls back to popularity if nothing fires.

## duplicate-product sensitivity

the same support 0.005, confidence 0.2, low-memory setting and unlimited itemset length were also tested after joining the two baguette labels with boolean or. all 1,000,000 baskets remain. the alternate representation has 97 features and 8,376,828 true entries, compared with 8,379,837 in the primary matrix. its combined baguette count is 108,610, with no double-counting of the 3,009 overlapping baskets.

| representation | itemsets | raw rules | retained rules | coverage | time seconds | peak mib |
| --- | --- | --- | --- | --- | --- | --- |
| original 98 products | 7,106 | 28,433 | 11,059 | 58/98 (59.18%) | 25.664 | 398.250 |
| merged 97 features | 7,142 | 28,482 | 11,094 | 58/97 (59.79%) | 25.652 | 441.344 |

the coverage denominators differ because one column now describes a bread family. a changed percentage alone is not evidence of a better recommender. the pair's different seasonal and co-purchase profiles, and the lost confidence-qualified link after merging, support keeping both catalogue records separate. the original 98-product application model remains the final model. see [the duplicate-product report](duplicate_products.md) for the full scan and rule comparison.

## seasonal runs

both seasonal runs use support 0.005, confidence 0.20 and low_memory=true.

| season | baskets | itemsets | rules | time seconds | peak memory mib |
| --- | --- | --- | --- | --- | --- |
| summer | 252,474 | 9,867 | 64,011 | 9.893 | 308.484 |
| winter | 246,965 | 6,042 | 18,348 | 5.268 | 209.766 |

the same rule must be compared using each season's own basket count and product baseline. charcoal to beef steak has lower winter support and confidence but higher winter lift. the notebook reports all three metrics, rather than treating high lift as high frequency.

the `ketchup, burger buns, beef steak -> relish` rule is mined in summer and not in winter. winter still has 877 joint baskets, but 0.35511% support is below the 0.5% threshold. this is a mining-threshold disappearance, not a claim that the joint event never happens. the directly calculated winter confidence is 35.08% and lift is 12.99075.

## limits and next steps

1. basket rules leave rare and new products uncovered. add category-based suggestions and controlled exploration, then measure the coverage and relevance changes.
2. a co-purchase pattern cannot show present intent or extra revenue. refresh rules monthly on recent baskets, compare with a popularity baseline in a held-out test and evaluate business value with a controlled shop experiment.

the application reads saved files only. re-mining is a separate offline step, and no scheduled or remote jobs were created.
