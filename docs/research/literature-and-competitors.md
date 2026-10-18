# Literature and Competitor Scan (narrow)

Access date for every entry: **2026-10-13**. Method: a handful of web searches plus page fetches. This is not a systematic review. Anything not opened and read is marked **unverified**. Dates are given only where a page stated them.

## 1. Verified sources (page opened this phase)

| Source | URL | Date | What was verified |
|---|---|---|---|
| Kapoor et al., *REFORMS: Reporting Standards for Machine Learning Based Science* (19 authors) | https://arxiv.org/abs/2308.07832 | v1 2023-08-15, v2 2023-09-19 | 32-question reporting checklist for ML-based science, aimed at validity, reproducibility, generalisability. Used as the reporting template for the experiment protocol. |
| GitHub Docs, *Rate limits for the REST API* | https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api | undated page | 60/h unauthenticated per IP, 5,000/h with a token, secondary limits. |

## 2. Seen in search results only (not opened — treat as unverified)

| Item | URL | Note |
|---|---|---|
| Sekeroglu et al., systematic review on ML and student performance prediction (*Applied Sciences*, 2021 per search listing) | https://doaj.org/article/10e9af06eb134a51901561ed1ec908d2 | Fetch of the publisher page returned 403. Found by search only; title/year as listed there. Broader than placement. |
| Balaji et al., systematic review of algorithms and features in academic performance prediction (*Applied Sciences*, 2021 per listing) | https://doaj.org/article/78d78c1c25a046559407ed1e40ccea1e | Not opened. |
| Kapoor & Narayanan, *Leakage and the reproducibility crisis in machine-learning-based science* (*Patterns*, 2023) | not opened | Known only via secondary descriptions; counts of affected papers varied between sources (294 vs 329), so no figure is used. |
| Kaggle "Campus Recruitment" style placement data (≈215 rows, 14–15 columns, `status` target; MBA-school context per an Analytics Vidhya tutorial) | https://www.analyticsvidhya.com/blog/2023/03/campus-recruitment-a-classification-problem-with-logistic-regression/ ; OpenML mirror https://www.openml.org/d/43616 | OpenML fetch returned no content; Kaggle page not opened. Row count, license, and provenance unverified. Fields reported: school percentages, specialization, work experience, salary. No GitHub/LeetCode features. |
| Placement-prediction papers (e.g. IJRASET 2020; IIETA "A Machine Learning Framework for Predicting Student Placement Outcomes") | https://iieta.org/node/21236 | Search snippets only. Reported accuracies (82–86%, and "perfect" in one student assignment on Scribd) are on tiny datasets and unverified; the perfect-score claim is itself a warning sign of overfitting or leakage. |

## 3. Products (from search snippets; capabilities unverified)

| Product | Source | Claimed |
|---|---|---|
| Placq | https://www.producthunt.com/products/placq | B2B tool for Indian colleges; syncs LeetCode, GitHub, HackerRank; DSA progress vs company benchmarks. |
| Leapath | https://softwarefinder.com/hr/leapath | Institution/recruiter tool; weighted readiness score from skills assessments; listed price unverified. |
| GitSignal AI (open source) | https://github.com/nirvik34/github_analyzer | GitHub profile "Portfolio Score" with LLM-written strengths/weaknesses. |
| PlaceWise | https://peerlist.io/vishnumashalkar/project/placewise--placement-readiness-platform | Resume-based readiness score. |

Searches did not surface PrepInsta, Naukri Campus, or HackerRank certification, so nothing is claimed about them. No product reviewed documents a validated outcome label.

## 4. What this supports (hypotheses, not findings)

- The space has readiness-score products that aggregate coding profiles; the novelty is not "a score". A defensible differentiator is provenance-labelled data plus honest claim boundaries (PRD §5.3 hypotheses).
- Public placement datasets found are small, academic/demographic, and lack the features PIS collects. They cannot validate PIS features.
- Reported accuracies in the placement literature on ~200-row data are not evidence of external validity.

## 5. Simpler baselines relevant to the chosen task

Persistence (last value), historical mean, seasonal-naive, and Poisson/logistic regression on lagged counts. The repo already has dummy baselines in `ml/train.py`, but on a 2-row test split (Phase 1 §3).

## 6. Product feature vs research contribution

Showing a score, radar chart, or gap rules is a product feature and exists elsewhere. A contribution would be a leakage-safe, reproducible evaluation of a stated task on real data, with documented negative results allowed.
