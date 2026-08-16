from fastapi import FastAPI, HTTPException
import os
from pydantic import BaseModel
from pymongo import MongoClient
import httpx


app = FastAPI(
    title="Booking Service",
    description="Microservice responsible for event bookings",
    version="1.0.0"
)


client = MongoClient(
    os.getenv("MONGO_URL", "mongodb://localhost:27017")
)

db = client["booking_db"]
bookings_collection = db["bookings"]


USER_SERVICE_URL = os.getenv(
    "USER_SERVICE_URL",
    "http://127.0.0.1:8001"
)

EVENT_SERVICE_URL = os.getenv(
    "EVENT_SERVICE_URL",
    "http://127.0.0.1:8002"
)


class BookingCreate(BaseModel):
    user_id: str
    event_id: str


@app.get("/")
def root():
    return {
        "message": "Booking Service is running",
        "service": "booking-service"
    }


@app.get("/health")
def health_check():
    try:
        client.admin.command("ping")

        return {
            "status": "healthy",
            "database": "connected",
            "service": "booking-service"
        }

    except Exception:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "service": "booking-service"
        }


@app.post("/bookings")
def create_booking(booking: BookingCreate):

    # Check User Service
    try:
        user_response = httpx.get(
            f"{USER_SERVICE_URL}/users",
            timeout=5
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="User Service is unavailable"
        )

    if user_response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail="Could not verify user"
        )

    users = user_response.json()

    user_exists = any(
        user["id"] == booking.user_id
        for user in users
    )

    if not user_exists:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Check Event Service
    try:
        event_response = httpx.get(
            f"{EVENT_SERVICE_URL}/events/{booking.event_id}",
            timeout=5
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Event Service is unavailable"
        )

    if event_response.status_code != 200:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    event = event_response.json()

    # Save booking
    result = bookings_collection.insert_one({
        "user_id": booking.user_id,
        "event_id": booking.event_id
    })

    return {
        "message": "Booking created successfully",
        "booking_id": str(result.inserted_id),
        "user": user_exists,
        "event": event["name"]
    }


@app.get("/bookings")
def get_bookings():

    bookings = []

    for booking in bookings_collection.find():

        bookings.append({
            "id": str(booking["_id"]),
            "user_id": booking["user_id"],
            "event_id": booking["event_id"]
        })

    return bookings