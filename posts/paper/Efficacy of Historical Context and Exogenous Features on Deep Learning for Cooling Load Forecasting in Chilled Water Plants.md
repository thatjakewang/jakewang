---
title: "Efficacy of Historical Context and Exogenous Features on Deep Learning for Cooling Load Forecasting in Chilled Water Plants"
date: 2026-09-15
category: summaries
slug: cooling-load-historical-context-ulfath-2026
authors:
  - Rubaiath E. Ulfath
  - Chi-Tsun Cheng
  - Toh Yen Pang
  - Iain Stewart
venue: "Scientific Reports, 2026"
doi: "10.1038/s41598-026-59706-1"
---

# Efficacy of Historical Context and Exogenous Features on Deep Learning for Cooling Load Forecasting in Chilled Water Plants

**Authors:** Rubaiath E. Ulfath, Chi-Tsun Cheng, Toh Yen Pang, Iain Stewart  
**Venue:** *Scientific Reports*, 2026  
**DOI:** 10.1038/s41598-026-59706-1

## Why I Read This Paper

Most cooling-load forecasting papers focus on proposing a new model or comparing forecasting accuracy across models. This paper asks a more practical question:

> **Given a forecasting model, how should we configure the historical context, temporal resolution, and exogenous features?**

Instead of treating the look-back window (LBW) as a fixed hyperparameter, the authors systematically investigate how **historical context length, sampling resolution, and weather/calendar features** affect both forecasting accuracy and computational cost.

This is particularly interesting because many previous cooling-load studies use look-back windows between one and seven days without systematically examining whether those choices are actually optimal.

Rather than asking only *which model is best*, this paper studies the interaction among:

- model architecture,
- look-back window,
- temporal resolution,
- exogenous features,
- and computational cost.

That makes it especially useful as a practical forecasting study rather than a simple model leaderboard.

---

## Paper Abstract

This paper studies **day-ahead cooling load forecasting for chilled water plants (CWPs)** using real industrial operational data.

The authors evaluate several forecasting models:

- ARIMA
- XGBoost
- LSTM
- TCN
- TFT
- N-HiTS

The experiments vary three major input-design factors.

### Look-back window

The models are tested with historical windows of:

- 1 day
- 2 days
- 7 days
- 8 days
- 10 days
- 14 days

### Temporal resolution

Three sampling resolutions are evaluated:

- 2.5 minutes
- 5 minutes
- 1 hour

### Exogenous features

The study also evaluates whether adding external contextual variables improves forecasting performance. The external inputs are:

- calendar/day type,
- dry-bulb temperature,
- wet-bulb temperature.

The central finding is surprisingly simple:

> **More historical data and higher temporal resolution do not necessarily produce better forecasts.**

Across the evaluated configurations, a **7-day look-back window with hourly data and exogenous features** provides one of the strongest accuracy-computation trade-offs.

The best-performing configuration is N-HiTS with:

- a 7-day look-back window,
- 1-hour sampling resolution,
- and exogenous weather/calendar features.

Under this configuration, N-HiTS achieves a MASE of **1.88**, compared with **3.82** without exogenous features, corresponding to a **50.8% reduction in MASE**.

---

## Three Important Things

### 1. The Look-Back Window Matters More Than It First Appears

A basic forecasting design decision is how much historical data the model should see.

Many studies simply choose 24 hours, 48 hours, or seven days and treat the look-back window as a fixed hyperparameter. This paper instead makes LBW one of the main experimental variables.

For the deep-learning models, increasing the LBW from **1–2 days to approximately 7 days** substantially improves forecasting performance.

For example, with exogenous inputs:

| Model | 2-day LBW MASE | 7-day LBW MASE |
|---|---:|---:|
| TCN | 9.21 | 2.43 |
| LSTM | 7.93 | 3.82 |
| N-HiTS | 4.47 | 1.88 |

The authors argue that seven days works well because it captures one complete operational cycle:

> **weekday → weekend → weekday**

A weekly window allows the model to observe recurring patterns such as:

- weekday versus weekend demand,
- startup and shutdown behavior,
- occupancy-related load changes,
- weather-load interactions,
- and transitions between operating regimes.

The important lesson is therefore not simply that "longer history is better."

It is closer to:

> **The historical window should be long enough to capture the dominant operational cycle of the system.**

Going beyond seven days to 10 or 14 days does not consistently improve performance, so blindly increasing historical context may only add noise and computation.

---

### 2. Higher Temporal Resolution Is Not Necessarily Better

One of the most practically useful findings is that **hourly data often performs as well as, or better than, 2.5-minute and 5-minute data**.

For example, with a 7-day LBW, N-HiTS achieves:

| Resolution | RMSE |
|---|---:|
| 2.5 min | 469.62 |
| 5 min | 473.94 |
| **1 hour** | **264.91** |

At first glance, this seems counterintuitive.

Higher-frequency data contains more observations, so it might seem that the model should have access to more useful information. In practice, however, finer temporal resolution also introduces:

- short-term fluctuations,
- sensor noise,
- higher-dimensional inputs,
- more lag variables,
- and significantly higher computational cost.

The computational difference becomes especially clear with a 7-day LBW:

| Model | 1 hour | 5 min | 2.5 min |
|---|---:|---:|---:|
| N-HiTS | 36.4 s | 135 s | 297 s |
| XGBoost | 19.8 s | 2927.9 s | 33640 s |

The XGBoost result is particularly interesting.

Tree-based models are often considered computationally efficient. But when high-frequency time-series data is converted into many lagged features, the feature space becomes extremely large. This dramatically increases tree construction and split-evaluation cost.

This leads to an important engineering lesson:

> **More granular data is not free information. It may mostly add noise and computational complexity.**

For day-ahead chilled-water forecasting, hourly aggregation may therefore be a more practical representation when the objective is operational forecasting rather than capturing very short transient behavior.

---

### 3. Exogenous Features Help Deep Learning Models Understand Regime Changes

Historical cooling load tells the model what happened before, but it does not necessarily explain **why tomorrow may be different**.

This becomes especially important around:

- weekends,
- public holidays,
- unusually hot days,
- and other changes in operating conditions.

The paper therefore adds three external variables:

- calendar/day type,
- dry-bulb temperature,
- wet-bulb temperature.

The effect is particularly strong for the deep-learning models.

At a 7-day LBW:

| Model | Baseline MASE | + Exogenous Features |
|---|---:|---:|
| TCN | 4.08 | 2.43 |
| LSTM | 4.51 | 3.82 |
| TFT | 4.97 | 3.08 |
| **N-HiTS** | **3.82** | **1.88** |
| XGBoost | 3.09 | 3.11 |

N-HiTS improves by approximately **50.8%** after the external variables are added.

This is especially visible around public holidays.

XGBoost can learn normal weekday and weekend patterns relatively well, but in the paper's example it fails to recognize the May 1 public holiday and treats it more like a normal weekday, leading to substantial overprediction.

The deep-learning models benefit more from the additional contextual information because the weather and calendar variables help distinguish between different operating regimes.

The takeaway is broader than simply:

> "Weather features improve accuracy."

A more useful interpretation is:

> **Exogenous variables are most valuable when historical patterns alone cannot explain a regime change.**

---

## Most Glaring Deficiency

The biggest weakness of the study is not the model comparison.

It is the **dataset**.

The entire experiment is based on:

- one chilled water plant,
- one commercial building,
- one tropical climate,
- and approximately one month of data.

The dataset was recorded from **April 1 to May 3, 2023** at 5-minute resolution.

This creates a major generalization problem.

The experiments provide strong evidence that a 7-day LBW works well **for this specific plant during this specific period**, but they do not establish that seven days is universally optimal for chilled-water forecasting.

Different buildings can exhibit very different operational patterns.

For example:

- an office building may have strong weekday/weekend periodicity,
- a hospital may operate continuously,
- a hotel may follow occupancy-driven demand,
- a university may have semester and holiday effects,
- and different climates may introduce very different seasonal cooling patterns.

Even the explanation for why the 7-day LBW works well depends on the assumption that the dominant operating cycle is weekly.

That may not hold for every building.

Therefore, I would interpret the result as:

> **Seven days is a strong empirical configuration for this dataset, not yet a universal rule for chilled-water forecasting.**

The authors explicitly acknowledge this issue and state that the dataset does not fully capture seasonal variation and may not generalize across climates, seasons, buildings, and plant sites.

A second limitation is that the study uses a fixed forecasting framework based on sliding-window multi-step forecasting. Other forecasting strategies, such as recursive or direct formulations, could change the relative behavior of the models.

Finally, the deep-learning models use controlled hyperparameter budgets for fairness. This is reasonable for benchmarking, but it also means that the reported model rankings are partly conditional on the chosen search spaces and training budgets.

---

## Conclusions for Future Work

The authors suggest several natural extensions:

- longer datasets covering seasonal variability,
- multiple chilled water plants,
- different geographical regions,
- different building types,
- uncertainty quantification,
- hybrid or ensemble forecasting,
- more extensive hyperparameter optimization,
- and alternative multi-step forecasting strategies.

These are sensible extensions, but I think the more interesting research question goes one step further.

The current paper asks:

> **Which configuration works best for one chilled water plant?**

A more scalable next question is:

> **Can one forecasting model generalize across multiple buildings and chilled water plants?**

Instead of training an independent forecasting model for every site, we could train a **global model** using data from many buildings:

```text
Training buildings
        ↓
   Global model
        ↓
  Unseen building
```

The key questions then become:

1. Can a global model outperform independently trained single-building models?
2. Can the model generalize to a building that was never seen during training?
3. How much does building metadata such as usage type, floor area, or site information help?
4. How important are weather and calendar variables for cross-building generalization?
5. If zero-shot performance is insufficient, how much local historical data is needed for adaptation?
6. Does the optimal LBW remain seven days across different building types?
7. Does the best temporal resolution remain hourly when the dataset becomes much larger and more diverse?

This shifts the problem from **single-site forecasting** toward **cross-building generalization**.

That distinction matters because practical building-energy forecasting systems must eventually scale beyond one building.

A model that performs extremely well after being separately trained and tuned for every site may be less useful operationally than a slightly less accurate global model that can be deployed across hundreds of buildings.

For me, this is the most interesting direction suggested by this paper:

> **The next step is not just finding the best model configuration for one plant, but testing whether the learned forecasting knowledge can transfer across buildings.**

---

## My Takeaway

The most valuable contribution of this paper is not that N-HiTS wins the benchmark.

It is the demonstration that **forecasting performance depends heavily on how the problem is configured**.

Three choices are especially important:

1. how much history the model sees,
2. how finely the data is sampled,
3. and whether the model receives external contextual information.

For this dataset, the practical sweet spot is:

```text
N-HiTS
+ 7-day look-back window
+ hourly resolution
+ calendar features
+ dry-bulb temperature
+ wet-bulb temperature
```

This configuration provides the best overall balance between accuracy and computational efficiency.

The broader lesson is:

> **Better forecasting does not necessarily come from a more complex model or more granular data. It often comes from choosing the right representation of historical context and external information.**
