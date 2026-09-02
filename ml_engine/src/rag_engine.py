"""
RAG Engine Module for Psychological Stress AI

Uses TF-IDF Vectorizer & Cosine Similarity (with fallback to semantic embedding models)
to retrieve relevant clinical stress coping interventions from the knowledge base
matching the user's SHAP top stress drivers and stress risk classification.
"""

import os
import json
from typing import List, Dict, Any
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import joblib

KB_PATH = os.path.join(os.path.dirname(__file__), "..", "rag", "rag_knowledge_base.json")

class StressRAGEngine:
    def __init__(self, kb_file: str = KB_PATH):
        self.kb_file = kb_file
        self.knowledge_base = []
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.tfidf_matrix = None
        self.is_built = False
        
        self.load_knowledge_base()

    def load_knowledge_base(self):
        if os.path.exists(self.kb_file):
            with open(self.kb_file, "r", encoding="utf-8") as f:
                self.knowledge_base = json.load(f)
            self.build_index()

    def build_index(self):
        if not self.knowledge_base:
            return
            
        corpus = []
        for item in self.knowledge_base:
            text = f"{item['title']} {item['category']} {item['summary']} {' '.join(item['target_drivers'])}"
            corpus.append(text)
            
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self.is_built = True

    def retrieve_interventions(
        self,
        stress_level: str,
        top_shap_drivers: List[Dict[str, Any]],
        user_query: str = "",
        top_k: int = 3,
        emotion: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top-k evidence-based interventions relevant to user stress context.

        `emotion` (optional): dominant facial expression detected by the
        FER engine (e.g. "anger", "fear") — boosts interventions tagged
        with the matching `target_emotions` entry so coping advice is
        emotionally tailored.
        """
        if not self.is_built:
            self.build_index()
            
        driver_names = [d.get("feature", "") for d in top_shap_drivers]
        
        query_text = f"Stress level {stress_level} drivers {' '.join(driver_names)} {user_query} {emotion}"
        query_vec = self.vectorizer.transform([query_text])
        
        sim_scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # Boost items matching specific target drivers
        boosted_scores = sim_scores.copy()
        for idx, item in enumerate(self.knowledge_base):
            matching_drivers = set(item.get("target_drivers", [])).intersection(set(driver_names))
            boosted_scores[idx] += len(matching_drivers) * 0.25

            # Emotion-aware boost: interventions tagged for the detected emotion
            if emotion and emotion in item.get("target_emotions", []):
                boosted_scores[idx] += 0.4
            if stress_level and stress_level in item.get("stress_levels", []):
                boosted_scores[idx] += 0.15
            
        top_indices = np.argsort(boosted_scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            item = self.knowledge_base[idx].copy()
            item["relevance_score"] = float(np.round(boosted_scores[idx], 3))
            results.append(item)
            
        return results

    def save(self, filepath: str):
        joblib.dump({"knowledge_base": self.knowledge_base, "vectorizer": self.vectorizer, "is_built": self.is_built}, filepath)

    def load(self, filepath: str):
        data = joblib.load(filepath)
        self.knowledge_base = data["knowledge_base"]
        self.vectorizer = data["vectorizer"]
        self.is_built = data["is_built"]
        if self.knowledge_base:
            self.build_index()
