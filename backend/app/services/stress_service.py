"""
Stress Assessment Business Logic Service
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status
from backend.app.models.assessment import StressAssessment
from backend.app.schemas.assessment import StressAssessmentCreate, StressAssessmentResponse

class StressService:
    @staticmethod
    async def create_assessment(db: AsyncSession, user_id: str, data: StressAssessmentCreate) -> StressAssessment:
        # PSS-10 Total Score calculation (reverse score items 4, 5, 7, 8)
        reverse_items = [data.pss_q4, data.pss_q5, data.pss_q7, data.pss_q8]
        normal_items = [data.pss_q1, data.pss_q2, data.pss_q3, data.pss_q6, data.pss_q9, data.pss_q10]
        
        total_pss = sum(normal_items) + sum([4 - item for item in reverse_items])
        
        # Use real-time tracker data if provided, otherwise use assessment data
        heart_rate = data.tracker_heart_rate or data.heart_rate
        hrv_sdnn = data.tracker_hrv_sdnn or data.hrv_sdnn
        sleep_hours = data.tracker_sleep_hours or data.sleep_hours
        sleep_efficiency = data.tracker_sleep_efficiency or data.sleep_efficiency
        physical_activity_min = data.tracker_physical_activity_min or data.physical_activity_min
        work_hours = data.tracker_work_hours or data.work_hours
        screen_time_hours = data.tracker_screen_time_hours or data.screen_time_hours
        breaks_per_day = data.tracker_breaks_per_day or data.breaks_per_day
        sentiment_score = data.tracker_sentiment_score or data.sentiment_score
        anxiety_score = data.tracker_anxiety_score or data.anxiety_score
        
        assessment = StressAssessment(
            user_id=user_id,
            pss_q1=data.pss_q1, pss_q2=data.pss_q2, pss_q3=data.pss_q3,
            pss_q4=data.pss_q4, pss_q5=data.pss_q5, pss_q6=data.pss_q6,
            pss_q7=data.pss_q7, pss_q8=data.pss_q8, pss_q9=data.pss_q9,
            pss_q10=data.pss_q10,
            total_pss=total_pss,
            heart_rate=heart_rate,
            hrv_sdnn=hrv_sdnn,
            sleep_hours=sleep_hours,
            sleep_efficiency=sleep_efficiency,
            physical_activity_min=physical_activity_min,
            work_hours=work_hours,
            screen_time_hours=screen_time_hours,
            breaks_per_day=breaks_per_day,
            sentiment_score=sentiment_score,
            anxiety_score=anxiety_score,
            notes=data.notes
        )
        
        db.add(assessment)
        await db.commit()
        await db.refresh(assessment)
        return assessment

    @staticmethod
    async def get_user_assessments(db: AsyncSession, user_id: str, limit: int = 50) -> List[StressAssessment]:
        stmt = select(StressAssessment).where(StressAssessment.user_id == user_id).order_by(StressAssessment.created_at.desc()).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_assessment_by_id(db: AsyncSession, assessment_id: str, user_id: str) -> StressAssessment:
        stmt = select(StressAssessment).where(StressAssessment.id == assessment_id)
        res = await db.execute(stmt)
        assessment = res.scalars().first()
        if not assessment or assessment.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stress assessment record not found.")
        return assessment
