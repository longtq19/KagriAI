from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.weather_ai import enrich

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
    data = enrich([x.model_dump() for x in items])
    return data
