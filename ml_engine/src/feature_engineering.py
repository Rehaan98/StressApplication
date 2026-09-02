"""
Feature Engineering Module for Psychological Stress AI

Derives domain-specific bio-psychosocial indicators:
1. HRV-to-Heart-Rate Ratio (Autonomic nervous balance indicator)
2. Sleep Deficiency Index (Deviation from optimal 8h sleep & efficiency)
3. Work-Stress Factor (Ratio of screen time & work hours to breaks)
4. Composite Strain Index (Holistic bio-cognitive strain index)
"""

import pandas as pd
import numpy as np

def engineer_stress_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    
    # 1. HRV to Heart Rate Ratio (Higher is better autonomic flexibility)
    df["hrv_to_hr_ratio"] = np.round(df["hrv_sdnn"] / (df["heart_rate"] + 1e-5), 4)
    
    # 2. Sleep Deficiency Index (0 = Perfect, higher = severe sleep debt)
    sleep_debt = np.maximum(0, 8.0 - df["sleep_hours"])
    eff_loss = (100.0 - df["sleep_efficiency"]) / 100.0
    df["sleep_deficiency_index"] = np.round(sleep_debt * 0.7 + eff_loss * 3.0, 3)
    
    # 3. Work Stress Factor (Ratio of overload to rest opportunities)
    breaks_safe = np.maximum(1, df["breaks_per_day"])
    df["work_stress_factor"] = np.round((df["work_hours"] + df["screen_time_hours"]) / (breaks_safe * 2.0), 3)
    
    # 4. Composite Strain Index
    # Integrates psychological (PSS, anxiety, sentiment) with physiological strain
    df["composite_strain_index"] = np.round(
        (df["total_pss"] / 40.0) * 0.35 +
        (df["anxiety_score"] / 10.0) * 0.25 +
        (1.0 - (df["sentiment_score"] + 1.0) / 2.0) * 0.20 +
        df["sleep_deficiency_index"] * 0.20, 3
    )
    
    return df
