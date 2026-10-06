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

The ASHRAE Great Energy Predictor III (GEPIII) competition was a large-scale machine-learning benchmark for building energy prediction. The competition provided more than 20 million training observations from 2,380 energy meters across 1,448 buildings and evaluated predictions on more than 41 million public and private test observations.

The paper summarizes the competition design, dataset, winning workflows, shared notebooks, and lessons learned. One of the most important findings is that forecasting performance depended on the entire workflow rather than on model selection alone. In particular, preprocessing emerged as a key differentiator among high-performing solutions.

The competition dataset is also directly relevant to my research because Building Data Genome Project 2 (BDG2) extends the public GEPIII data with additional buildings. This makes the competition a useful reference for both data preparation and experimental design in my chilled-water demand forecasting study.

## Why I Chose This Paper

I chose this paper for three main reasons.

### 1. Dataset Relevance

BDG2 extends the public GEPIII data, so the competition is closely connected to the dataset used in my research.

### 2. EDA and Preprocessing Reference

The competition intentionally applied only minimal initial cleaning so that participants had to deal with real-world data-quality issues themselves. This makes the winning solutions useful references for visualization-based EDA, anomaly detection, missing-value handling, zero-value screening, and time alignment.

### 3. Experimental Design Reference

The competition used a temporal split:

- **2016:** training data
- **2017:** public test/validation data
- **2018:** private test data

It also used **RMSLE** as the evaluation metric. RMSLE reduces the dominance of high-consumption meters, which is relevant to a global-model setting where buildings may have very different cooling-demand scales.

For my study, I plan to test RMSLE as an additional evaluation metric rather than relying on it alone.

## Three Important Things

### 1. Visualization-Based EDA Should Come Before Modeling

One of the useful lessons from GEPIII is that data problems are often easier to identify visually than through summary statistics alone.

The second-place team manually inspected meter data using visualization and removed abnormal behavior before model training. This shows that EDA is not just a reporting step; it can directly influence preprocessing decisions.

For my own work, I want to use visualizations at the beginning of the pipeline to understand:

- building-type distributions
- floor-area distributions
- missing values
- zero periods
- constant-value periods
- abnormal peaks
- differences among buildings and sites

### 2. Preprocessing Is Part of the Modeling Workflow

The winning teams used different preprocessing strategies:

| Rank | Main preprocessing strategy |
| --- | --- |
| 1st | Removed meter anomalies, imputed missing weather values, corrected time zones |
| 2nd | Visual analytics and manual inspection |
| 3rd | Removed zero values occurring in the same period and site |
| 4th | Deleted outliers during training |
| 5th | Removed long constant-value streaks and zero target values |

The important lesson is not that one of these rules should always be copied. Instead, the competition shows that data quality must be treated as part of the forecasting workflow.

This is especially important for chilled-water data because a zero value may indicate either a real system shutdown or a data-quality problem. Therefore, zero values should not be removed automatically without checking the operating context.

### 3. Evaluation Across Heterogeneous Buildings Requires Scale Awareness

RMSE can be strongly influenced by large buildings or high-consumption meters because absolute errors are squared.

RMSLE instead compares values after a logarithmic transformation:

```text
                  n
RMSLE = sqrt( 1/n * Σ  [ log(ŷ_i + 1) - log(y_i + 1) ]^2 )
                 i=1
```

This makes it useful when evaluating a global model across buildings with very different demand scales.

However, RMSLE also compresses large absolute errors, so I do not plan to use it as the only metric. RMSE and MASE can still provide complementary information about absolute forecasting error and scale-independent performance.

## Critical Review

### No Single Transferable Cleaning Recipe

The paper reports successful preprocessing strategies from different winning teams, but it does not define a reusable standard procedure.

This means the competition provides useful references, but not a universal cleaning rule that can be directly applied to every building-energy dataset.

For my research, the preprocessing rules still need to be validated specifically for chilled-water demand.

### The Effect of Each Cleaning Step Is Not Isolated

The winning workflows combine:

- preprocessing
- feature engineering
- model selection
- ensemble modeling
- postprocessing

Because these components are used together, the contribution of each individual cleaning step is not evaluated separately.

For example, the first-place solution used anomaly removal, weather imputation, timezone correction, 28 engineered features, multiple models, and ensemble averaging. The paper shows that the complete workflow performed well, but it does not quantify how much improvement came from each preprocessing step.

### Competition Workflows May Not Directly Transfer to Deployment

Some winning solutions relied on public data, complex ensembles, and competition-specific tuning.

These approaches are useful for benchmarking, but a real operational forecasting system must also consider:

- computational cost
- interpretability
- maintainability
- data availability
- robustness after deployment

Therefore, I treat this paper as a **workflow reference**, not as direct evidence that one particular competition solution should be deployed unchanged.

## Applying This to My Research

My current work focuses on the metadata of the chilled-water subset in BDG2.

### Chilled-Water Building Selection

The full metadata contains **1,636 buildings**.

After selecting buildings with chilled-water meters:

**1,636 buildings → 555 chilled-water buildings**

This subset becomes the starting population for my cooling-demand forecasting study.

### Primary Space Usage

The chilled-water subset is dominated by education and office buildings.

This indicates that the building-type distribution is imbalanced, which may influence a global model because the model will see more examples from the dominant categories.

### Sub-Primary Space Usage

The sub-primary space usage distribution is even more detailed and shows a clear long-tail pattern.

The four largest categories are:

- Office
- College Classroom
- College Laboratory
- Dormitory

Together, these categories account for approximately **63.4%** of the chilled-water buildings.

At the same time, **101 buildings** are distributed across many low-frequency subcategories.

This suggests that `sub_primaryspaceusage` may provide useful contextual information, but rare categories may need to be grouped or evaluated carefully.

### Building Floor Area

The building floor-area distribution is strongly right-skewed.

Most buildings are relatively small, while a small number of buildings are substantially larger.

This matters for global modeling because large differences in floor area may lead to large differences in cooling-demand magnitude. It also reinforces the need to use evaluation metrics that are not dominated by the largest buildings.

## Current Progress

The current preprocessing status is:

- **Phase 1: Metadata — completed**
- **Phase 2: Chilled-water meter data — next**
- **Phase 3: Weather data — next**
- **Phase 4: Data integration and final preprocessing — planned**

At this stage, I would describe the work as **initial metadata screening and EDA**, rather than completed preprocessing.

## Next Steps

The next step is to profile the chilled-water meter data for each building.

I plan to examine:

- missing-data rate
- zero-value rate
- longest zero streak
- constant-value periods
- extreme values
- distribution statistics
- time-series patterns
- coverage across 2016 and 2017

After that, I will process the weather data, including missing values and time alignment, and then integrate metadata, chilled-water demand, and weather data into a model-ready dataset.

## My Research Direction

The longer-term goal is to develop a global chilled-water demand forecasting model across multiple buildings.

Instead of training an independent model for every building, I want to investigate whether one forecasting model can learn from a heterogeneous portfolio of buildings while using building metadata as contextual information.

The current EDA already shows two challenges that will matter later:

1. **Building categories are imbalanced.**
2. **Building sizes vary substantially.**

These differences may affect how well a global model generalizes across building types and demand scales.

A possible extension is to compare:

- individual building models
- one global model
- cluster-specific models
- a global model with cluster or building-context features

The GEPIII paper does not provide a direct answer to these questions, but it provides a useful methodological lesson: **before comparing forecasting models, the data pipeline must be carefully understood, visualized, and validated.**

## My Takeaway

The main value of this paper for my research is not a specific winning algorithm.

The most important lesson is that building-energy forecasting performance depends on the entire workflow:

**EDA → Preprocessing → Feature Engineering → Modeling → Evaluation**

For my BDG2 chilled-water study, this means I should first build a defensible and reproducible data-preprocessing pipeline before moving to global-model comparison.
