from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class WeatherItem(BaseModel):
    status: Optional[str] = None
    timestamp: Optional[str] = None
    topic: Optional[str] = None
    topic_name: Optional[str] = None
    value: Optional[float] = None
    phase: Optional[str] = None
    recomment: Optional[str] = None
    warning: Optional[str] = None
    plant: Optional[str] = None
    phaseName: Optional[str] = None

class WeatherData(BaseModel):
    getRecommenedWeather: list[WeatherItem] = []

class WeatherRequest(BaseModel):
    data: WeatherData

@router.post("/api/kagriai/weather")
async def recommendations_weather(req: WeatherRequest):
    items = req.data.getRecommenedWeather if req and req.data else []
    warnings = []
    recommendations = []
    warning_set = set()
    recommend_set = set()
    for it in items:
        w = (it.warning or "").strip()
        r = (it.recomment or "").strip()
        if w:
            if w not in warning_set:
                warning_set.add(w)
                warnings.append(w)
        if r:
            if r not in recommend_set:
                recommend_set.add(r)
                recommendations.append(r)
    warnings_out = [{"id": i + 1, "content": w} for i, w in enumerate(warnings)]
    recommendations_out = [{"id": i + 1, "content": r} for i, r in enumerate(recommendations)]
    return {"Warnings": warnings_out, "Recommendations": recommendations_out}
