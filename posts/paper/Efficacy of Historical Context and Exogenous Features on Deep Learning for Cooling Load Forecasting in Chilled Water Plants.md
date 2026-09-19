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
---

# Efficacy of Historical Context and Exogenous Features on Deep Learning for Cooling Load Forecasting in Chilled Water Plants

**Authors:** Rubaiath E. Ulfath, Chi-Tsun Cheng, Toh Yen Pang, Iain Stewart  
**Venue:** *Scientific Reports*, 2026  
**DOI:** 10.1038/s41598-026-59706-1

## Paper Abstract
Day-ahead cooling load forecasting for chilled water plants (CWPs) is essential for efficient energy management, yet most literature focuses on model comparisons rather than input formulation. This paper systematically evaluates the influence of historical context length (look-back window: 1 to 14 days), temporal sampling resolution (2.5 minutes, 5 minutes, 1 hour), and exogenous environmental/calendar variables on models including ARIMA, XGBoost, LSTM, TCN, TFT, and N-HiTS using real industrial operational data. Counter to the intuition that denser data yields superior predictions, results indicate that excessive granularity introduces sensor noise and computational bloat without performance gains. A 7-day look-back window combined with 1-hour resolution and exogenous weather/calendar features delivers the optimal accuracy-computation trade-off. Under this configuration, N-HiTS achieves the strongest overall performance with a MASE of 1.88, representing a 50.8% error reduction relative to the univariate baseline.

## Three Important Things
### 1. More Data & Higher Granularity Do Not Mean Better Forecasts

A common assumption in deep learning is to feed the model the finest resolution available. Here, 1-hour aggregation consistently matched or beat 2.5-minute and 5-minute sampling (e.g., N-HiTS RMSE dropped from 469.62 at 2.5-min to 264.91 at 1-hour). High-frequency sampling simply floods the model with high-frequency sensor noise and expands the feature space, leading to astronomical computational costs without accuracy benefits (XGBoost jumped from 19.8 seconds to 33,640 seconds). For day-ahead planning, high-frequency transients are irrelevant noise.

### 2. The Look-Back Window Must Align with the Dominant Operational Cycle

Arbitrarily picking a 24-hour or 48-hour history handicaps the architecture. Deep learning models experienced massive performance leaps when the look-back window expanded from 2 days to 7 days (N-HiTS MASE plunged from 4.47 to 1.88; TCN from 9.21 to 2.43). A 7-day span is the exact structural duration required to capture an entire operational loop: weekday occupancy, weekend shutdowns, and transition ramps. Pushing history further to 10 or 14 days yielded diminishing returns and unnecessary lag features.

### 3. Exogenous Features Are Required for Regime Changes

Autoregressive history explains recurring inertia, but fails when the environment forces an operational deviation. Introducing dry-bulb temperature, wet-bulb temperature, and calendar/day types cut N-HiTS error by over 50%. This gap was obvious during unusual periods like the May 1st public holiday: tree-based models lacking context treated it like an ordinary high-load weekday and severely overpredicted, whereas deep models leveraging external calendar/weather cues recognized the regime shift immediately.

## Conclusions

The standard next steps are obvious: multi-year validation across divergent climate zones, varied building typologies (hospitals, universities, data centers), and formal uncertainty quantification.

The truly impactful direction, however, is cross-building transferability. Real-world CWP optimization cannot afford isolated hyperparameter searches and dedicated training runs for every individual plant. The logical leap is building a unified global model: can a pre-trained network ingest sparse site metadata (tonnage, facility category, climate code) and perform zero-shot or few-shot inference on an unseen chiller plant? Determining whether the 7-day/1-hour sweet spot holds across diverse building portfolios will decide if these pipelines scale in production.