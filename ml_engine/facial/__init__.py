"""
Facial Expression Recognition & Stress Estimation Package

Uses a CNN trained on the FER2013 dataset (emotion-ferplus-8 ONNX model,
7 + contempt expression classes) for real-time emotion classification and
maps detected expressions to a continuous stress score using
valence/arousal affect science.
"""

from ml_engine.facial.fer_detector import FacialStressAnalyzer, EMOTION_LABELS, EMOTION_STRESS_MAP

__all__ = ["FacialStressAnalyzer", "EMOTION_LABELS", "EMOTION_STRESS_MAP"]
