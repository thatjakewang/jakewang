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

## Paper Summary
Day-ahead cooling load forecasting for chilled water plants (CWPs) is essential for efficient energy management, yet most literature focuses on model comparisons rather than input formulation. This paper systematically evaluates the influence of historical context length (look-back windows of 1, 2, 7, 8, 10, and 14 days), temporal sampling resolution (2.5 minutes, 5 minutes, and 1 hour), and exogenous environmental and calendar variables on models including ARIMA, XGBoost, LSTM, TCN, TFT, and N-HiTS using real industrial operational data.

Higher temporal resolution does not necessarily improve forecasting accuracy, as very high-resolution data may introduce additional noise and computational burden without meaningful performance gains. A 7-day look-back window combined with 1-hour resolution and exogenous weather and calendar features provides the best accuracy–computation trade-off. Under this configuration, N-HiTS achieves the strongest overall performance with a MASE of 1.88, representing a 50.8% reduction in error relative to the univariate baseline.

## Three Important Things
### 1. Higher Temporal Resolution Does Not Necessarily Improve Forecasting

A common assumption in deep learning is that finer temporal resolution should improve forecasting performance. However, in this study, 1-hour aggregation matched or outperformed 2.5-minute and 5-minute sampling in several cases. For example, N-HiTS RMSE decreased from 469.62 at 2.5-minute resolution to 264.91 at 1-hour resolution.

Higher-frequency data introduced more noise and substantially increased computational cost without consistent accuracy gains. For XGBoost, training time increased from 19.8 seconds at 1-hour resolution to 33,640 seconds at 2.5-minute resolution. For day-ahead forecasting, hourly data therefore provided a more favorable accuracy–efficiency trade-off.


### 2. The Look-Back Window Should Reflect the Dominant Operational Cycle

Short look-back windows of only 1 or 2 days may not capture the full weekly operating pattern of chilled water plants. Deep learning models improved substantially when the look-back window increased to 7 days; for example, N-HiTS MASE decreased from 4.47 at 2 days to 1.88 at 7 days, while TCN decreased from 9.21 to 2.43.

A 7-day window likely performs well because it captures a complete weekly cycle, including weekday operation, weekends, and transitions between them. Extending the history further to 10 or 14 days generally provided limited additional benefit while increasing computational complexity, making 7 days a favorable accuracy–efficiency trade-off.

### 3. Exogenous Features Improve Adaptation to Regime Changes

Historical cooling load captures recurring operational patterns, but may be insufficient when operating conditions change. Adding dry-bulb temperature, wet-bulb temperature, and calendar features reduced N-HiTS MASE from 3.82 to 1.88, corresponding to a 50.8% reduction in error.

During public holidays, historical load patterns alone may be insufficient to represent changes in building operation. In the study, XGBoost overestimated the load on a public holiday, while deep learning models benefited more from calendar and weather features in adapting to such regime changes.

## Research gap

The study is based on only one chilled water plant in a tropical climate and approximately one month of operational data. Therefore, the identified optimal configuration may not generalize to different building types, climates, seasons, or operating patterns.

## Research Extension

Instead of training and tuning an independent model for each building, a potential research direction is to develop a global forecasting model trained across multiple buildings. Building-specific metadata, such as building type, floor area, climate zone, operating schedule, and system capacity, could be incorporated as contextual features. The key question is whether a robust combination of look-back window, temporal resolution, exogenous variables, and model architecture can generalize across heterogeneous buildings.