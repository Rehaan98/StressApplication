"""
Synthetic Psychological Stress Dataset Generator

Generates a realistic multi-modal psychological stress dataset combining:
1. PSS-10 (Perceived Stress Scale) questionnaire items (10 items, scale 0-4)
2. Physiological markers: Heart Rate (bpm), HRV (SDNN in ms), Sleep Hours, Sleep Efficiency (%), Physical Activity (mins/day)
3. Workload & Environmental markers: Daily Work Hours, Screen Time, Daily Breaks
4. Cognitive & Sentiment markers: Self-reported sentiment score (-1.0 to 1.0), Anxiety self-rating (1-10)
5. Ground Truth Target: Stress Risk Level (0: Low, 1: Moderate, 2: High, 3: Severe)

Class boundaries are calibrated to percentiles of the composite risk distribution
(15% / 50% / 25% / 10% by default), mirroring how population-calibrated clinical
risk models set severity cutoffs. This guarantees every class - including Severe -
is represented in the training data.
"""

import os
import json
import numpy as np
import pandas as pd

def generate_stress_dataset(
    n_samples: int = 2500,
    random_state: int = 42,
    label_noise: float = 0.015,
    threshold_moderate: float = None,
    threshold_high: float = None,
    threshold_severe: float = None,
    low_share: float = 0.15,
    moderate_share: float = 0.50,
    high_share: float = 0.25,
) -> pd.DataFrame:
    np.random.seed(random_state)
    
    # 1. PSS-10 items (10 items: 0=Never to 4=Very Often)
    # Items 4, 5, 7, 8 are positively phrased (reverse scored in real PSS, here raw responses)
    # Distribution is right-skewed so the full 0-4 range (and extreme totals) is represented,
    # which keeps the "Severe" stress class reachable in the dataset.
    pss_items = {}
    for i in range(1, 11):
        pss_items[f"pss_q{i}"] = np.random.choice([0, 1, 2, 3, 4], size=n_samples, p=[0.10, 0.18, 0.28, 0.28, 0.16])
    
    pss_df = pd.DataFrame(pss_items)
    
    # Total PSS Score calculation (reverse score items 4, 5, 7, 8)
    reverse_cols = ["pss_q4", "pss_q5", "pss_q7", "pss_q8"]
    pss_score = pss_df.copy()
    for col in reverse_cols:
        pss_score[col] = 4 - pss_score[col]
    total_pss = pss_score.sum(axis=1)
    
    # 2. Physiological Features
    # Low stress -> Higher HRV, moderate HR, better sleep
    # High stress -> Lower HRV, higher HR, poor sleep
    stress_latent = total_pss / 40.0 # Normalize 0-1
    
    heart_rate = np.round(60 + stress_latent * 35 + np.random.normal(0, 5, n_samples), 1)
    heart_rate = np.clip(heart_rate, 50, 120)
    
    hrv_sdnn = np.round(80 - stress_latent * 50 + np.random.normal(0, 8, n_samples), 1)
    hrv_sdnn = np.clip(hrv_sdnn, 15, 120)
    
    sleep_hours = np.round(8.5 - stress_latent * 3.5 + np.random.normal(0, 0.8, n_samples), 1)
    sleep_hours = np.clip(sleep_hours, 3.5, 10.0)
    
    sleep_efficiency = np.round(92 - stress_latent * 30 + np.random.normal(0, 5, n_samples), 1)
    sleep_efficiency = np.clip(sleep_efficiency, 45, 99)
    
    physical_activity_min = np.round(60 - stress_latent * 45 + np.random.normal(0, 12, n_samples), 0)
    physical_activity_min = np.clip(physical_activity_min, 0, 120)
    
    # 3. Workload Features
    work_hours = np.round(6.0 + stress_latent * 6.0 + np.random.normal(0, 1.2, n_samples), 1)
    work_hours = np.clip(work_hours, 4.0, 16.0)
    
    screen_time_hours = np.round(3.0 + stress_latent * 5.0 + np.random.normal(0, 1.0, n_samples), 1)
    screen_time_hours = np.clip(screen_time_hours, 1.0, 14.0)
    
    breaks_per_day = np.round(5.0 - stress_latent * 3.5 + np.random.normal(0, 0.8, n_samples), 0)
    breaks_per_day = np.clip(breaks_per_day, 0, 8)
    
    # 4. Cognitive & Sentiment
    sentiment_score = np.round(0.6 - stress_latent * 1.2 + np.random.normal(0, 0.2, n_samples), 2)
    sentiment_score = np.clip(sentiment_score, -1.0, 1.0)
    
    anxiety_score = np.round(1 + stress_latent * 8.5 + np.random.normal(0, 0.8, n_samples), 1)
    anxiety_score = np.clip(anxiety_score, 1.0, 10.0)
    
    # 5. Composite Stress Risk Level (0: Low, 1: Moderate, 2: High, 3: Severe)
    # Calculated based on weighted combination of PSS, HRV, Sleep, and Sentiment.
    # Small label noise models real-world boundary ambiguity and guarantees that
    # every class (including Severe) is represented in the training data.
    composite_index = (
        0.40 * (total_pss / 40.0) +
        0.25 * (1.0 - (hrv_sdnn / 120.0)) +
        0.20 * (1.0 - (sleep_hours / 10.0)) +
        0.15 * ((anxiety_score - 1.0) / 9.0)
    )
    # Small label noise models real-world boundary ambiguity and clinical
    # measurement error at the Low/Moderate/High/Severe cutoffs.
    composite_index = np.clip(
        composite_index + np.random.normal(0, label_noise, n_samples), 0.0, 1.0
    )

    low_share = min(max(low_share, 0.01), 0.5)
    moderate_share = min(max(moderate_share, 0.05), 0.8)
    high_share = min(max(high_share, 0.02), 0.5)
    severe_share = max(1.0 - low_share - moderate_share - high_share, 0.01)

    if threshold_moderate is None:
        threshold_moderate = float(np.quantile(composite_index, low_share))
    if threshold_high is None:
        threshold_high = float(np.quantile(composite_index, low_share + moderate_share))
    if threshold_severe is None:
        threshold_severe = float(np.quantile(composite_index, low_share + moderate_share + high_share))

    stress_class = np.zeros(n_samples, dtype=int)
    stress_class[composite_index >= threshold_moderate] = 1  # Moderate
    stress_class[composite_index >= threshold_high] = 2      # High
    stress_class[composite_index >= threshold_severe] = 3    # Severe
    
    df = pd.DataFrame({
        "user_id": [f"USR-{1000 + i}" for i in range(n_samples)],
        **pss_items,
        "total_pss": total_pss,
        "heart_rate": heart_rate,
        "hrv_sdnn": hrv_sdnn,
        "sleep_hours": sleep_hours,
        "sleep_efficiency": sleep_efficiency,
        "physical_activity_min": physical_activity_min,
        "work_hours": work_hours,
        "screen_time_hours": screen_time_hours,
        "breaks_per_day": breaks_per_day,
        "sentiment_score": sentiment_score,
        "anxiety_score": anxiety_score,
        "stress_level": stress_class
    })
    
    return df

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    df = generate_stress_dataset(n_samples=3000)
    csv_path = os.path.join(out_dir, "synthetic_stress_data.csv")
    df.to_csv(csv_path, index=False)
    print(f"Generated synthetic stress dataset with {len(df)} records at {csv_path}")
