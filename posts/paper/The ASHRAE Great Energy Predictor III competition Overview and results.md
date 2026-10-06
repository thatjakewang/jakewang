---
title: "The ASHRAE Great Energy Predictor III Competition: Overview and Results"
date: 2026-10-06
category: summaries
slug: the-ashrae-gepiii-competition
authors:
  - Clayton Miller
  - Pandarasamy Arjunan
  - Anjukan Kathirgamanathan
  - Chun Fu
  - Jonathan Roth
  - June Young Park
  - Chris Balbach
  - Krishnan Gowri
  - Zoltan Nagy
  - Anthony Fontanini
  - Jeff Haberl
venue: "Science and Technology for the Built Environment, 2020"
---

# The ASHRAE Great Energy Predictor III Competition: Overview and Results

**Authors:** Clayton Miller et al.  
**Venue:** *Science and Technology for the Built Environment*, 2020  
**DOI:** 10.1080/23744731.2020.1795514

## Paper Summary
In late 2019, ASHRAE hosted the Great Energy Predictor III (GEPIII) machine learning competition on Kaggle, the third energy prediction competition from ASHRAE and the first since the mid-1990s. Competitors received over 20 million points of training data from 2,380 energy meters across 1,448 buildings from 16 sources, and were evaluated on more than 41 million public and private test observations. The competition attracted 4,370 participants across 3,614 teams from 94 countries, who submitted 39,403 predictions. This paper documents the competition design, dataset, winning workflows, and lessons learned.

The most accurate solutions used large ensembles of gradient boosting tree models, particularly LightGBM, rather than any single novel architecture. The more important finding is that forecasting performance depended on the entire workflow rather than on model selection alone: as in the first ASHRAE competition, preprocessing of the data sets emerged as the key differentiator among high-performing solutions. Beyond the top five winning workflows, competitors publicly shared 415 reproducible notebooks, including over 40 additional full solutions.

## Three Important Things
### 1. Visualization-Based EDA Should Precede Modeling

The competition organizers intentionally applied only minimal initial cleaning, so participants had to confront real-world data-quality issues themselves. This design choice makes the winning solutions useful references for anomaly detection, missing-value handling, zero-value screening, and time alignment, because each team had to decide what counted as a defect before it could be removed.

A recurring lesson is that data problems are often easier to identify visually than through summary statistics alone. The second-place team manually inspected meter data using visual analytics and removed abnormal behavior before model training. This shows that exploratory data analysis is not merely a reporting step that precedes the real work; it directly determines which preprocessing decisions are made.

### 2. Preprocessing Is Part of the Modeling Workflow

The five winning teams converged on the importance of preprocessing but diverged on method. The first-place solution removed meter anomalies, imputed missing weather values, and corrected time zones; the second place relied on visual analytics and manual inspection; the third removed zero values occurring in the same period and site; the fourth deleted outliers during training; and the fifth removed long constant-value streaks and zero target values.

The lesson is not that any one of these rules should be copied directly, but that data quality must be treated as a component of the forecasting workflow rather than a preliminary chore. This matters especially for chilled-water data, where a zero value may indicate either a genuine system shutdown or a data-quality defect. Zero values therefore should not be removed automatically without first checking the operating context.

### 3. Evaluating Heterogeneous Buildings Requires Scale Awareness

The competition used RMSLE as its evaluation metric, computed as the root mean square of the differences between the logarithms of predicted and actual values after adding one to each. Because the comparison happens in log space, RMSLE reduces the dominance of high-consumption meters, whereas RMSE can be driven almost entirely by large buildings since absolute errors are squared.

This property makes RMSLE well suited to a global-model setting where buildings differ substantially in demand scale. It also compresses large absolute errors, however, so it should not serve as the only metric. RMSE and MASE still provide complementary information about absolute forecasting error and scale-independent performance respectively.

## Research gap

The paper reports the preprocessing strategies of successful teams but does not distill them into a reusable standard procedure, so the competition offers useful references rather than a cleaning rule that transfers to every building-energy dataset. The contribution of each individual step also remains unquantified, because the winning workflows combine preprocessing, feature engineering, model selection, ensemble modeling, and postprocessing together. The first-place solution, for instance, used anomaly removal, weather imputation, timezone correction, 28 engineered features, multiple models, and ensemble averaging; the paper shows that the complete workflow performed well without isolating how much came from each preprocessing decision.

A further limitation is that competition conditions differ from deployment conditions. Some winning solutions relied on public leaderboard data, complex ensembles, and competition-specific tuning, whereas an operational forecasting system must also satisfy constraints on computational cost, interpretability, maintainability, data availability, and robustness after deployment.

## Research Extension

Building Data Genome Project 2 (BDG2) extends the public GEPIII data with additional buildings, which makes the competition a direct reference for data preparation and experimental design in a chilled-water demand forecasting study. A natural extension is to develop a global chilled-water forecasting model trained across a heterogeneous portfolio of buildings, using building metadata as contextual information, and to compare it against independent per-building models, cluster-specific models, and a global model with cluster or building-context features. Because the paper provides no reusable cleaning recipe, the preprocessing rules it documents would first need to be validated specifically for chilled water, where the meaning of a zero value is ambiguous. The methodological lesson it does offer is that before comparing forecasting models, the data pipeline must be understood, visualized, and validated.
