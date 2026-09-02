"""
Facial Expression Analysis Business Logic Service

Runs CNN inference off the event loop (asyncio.to_thread) on a shared,
thread-safe singleton analyzer so the API remains responsive under load
and scales horizontally across uvicorn workers.
"""

import asyncio
import base64
import binascii
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from backend.app.models.facial_analysis import FacialAnalysis
from ml_engine.facial.fer_detector import FacialStressAnalyzer

analyzer_instance = FacialStressAnalyzer()

MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4MB per frame


class FacialService:
    @staticmethod
    async def analyze(db: AsyncSession, user_id: str, image_b64: str, source: str = "webcam") -> Dict[str, Any]:
        try:
            raw = base64.b64decode(image_b64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base64 image payload.")
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image exceeds 4MB limit.")
        if not raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image payload.")

        # Inference off the event loop: keeps the async server responsive at scale
        result = await asyncio.to_thread(analyzer_instance.analyze_image, raw)

        if result.get("error"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result["error"])
        if not result.get("face_detected"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No face detected in the frame.")

        probs = result["emotion_probabilities"] or {}
        dominant = result["dominant_emotion"]
        stress_score = result["stress_score"]
        stress_level = result["stress_level"]
        confidence = round(float(max(probs.values())) if probs else 0.5, 4)

        record = FacialAnalysis(
            user_id=user_id,
            dominant_emotion=dominant,
            emotion_probabilities=probs,
            stress_score=stress_score,
            stress_level=stress_level,
            confidence_score=confidence,
            model=result.get("model", "unknown"),
            face_detected=1 if result["face_detected"] else 0,
            num_faces=result.get("num_faces", 1),
            source=source,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        return {
            "id": record.id,
            "face_detected": result["face_detected"],
            "num_faces": result["num_faces"],
            "dominant_emotion": dominant,
            "emotion_probabilities": probs,
            "stress_score": stress_score,
            "stress_level": stress_level,
            "confidence_score": confidence,
            "model": result.get("model", "unknown"),
            "processing_ms": result.get("processing_ms", 0.0),
            "interventions": [],
        }

    @staticmethod
    async def history(db: AsyncSession, user_id: str, limit: int = 50) -> Dict[str, Any]:
        stmt = (
            select(FacialAnalysis)
            .where(FacialAnalysis.user_id == user_id)
            .order_by(desc(FacialAnalysis.created_at))
            .limit(limit)
        )
        res = await db.execute(stmt)
        items = res.scalars().all()

        current_score = items[0].stress_score if items else None
        current_level = items[0].stress_level if items else None
        return {
            "items": [
                {
                    "id": it.id,
                    "dominant_emotion": it.dominant_emotion,
                    "emotion_probabilities": it.emotion_probabilities,
                    "stress_score": it.stress_score,
                    "stress_level": it.stress_level,
                    "confidence_score": it.confidence_score,
                    "source": it.source,
                    "created_at": it.created_at,
                }
                for it in items
            ],
            "total": len(items),
            "current_stress_score": current_score,
            "current_stress_level": current_level,
        }
