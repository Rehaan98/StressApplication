"""
PDF/CSV Report Generation Service
"""

import io
import csv
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.services.stress_service import StressService
from backend.app.services.analytics_service import AnalyticsService

class ReportService:
    @staticmethod
    async def generate_user_csv_report(db: AsyncSession, user_id: str) -> str:
        assessments = await StressService.get_user_assessments(db, user_id, limit=500)
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "Assessment ID", "Date", "Total PSS", "Heart Rate (bpm)",
            "HRV SDNN (ms)", "Sleep Hours", "Sleep Efficiency (%)",
            "Physical Activity (min)", "Work Hours", "Screen Time (hrs)",
            "Sentiment Score", "Anxiety Rating (1-10)"
        ])
        
        for a in assessments:
            writer.writerow([
                a.id, a.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                a.total_pss, a.heart_rate, a.hrv_sdnn, a.sleep_hours,
                a.sleep_efficiency, a.physical_activity_min, a.work_hours,
                a.screen_time_hours, a.sentiment_score, a.anxiety_score
            ])
            
        return output.getvalue()
