import requests
import config
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, ConfigDict

CAL_API_V2_BASE_URL = "https://api.cal.com/v2"  # For event-types
CAL_API_V1_BASE_URL = "https://api.cal.com/v1"  # For slots

# --- BaseModel definitions for API responses ---
class Location(BaseModel):
    model_config = ConfigDict(extra='allow')
    type: str
    address: str
    public: bool

class SlotItem(BaseModel):
    time: str

class SlotsResponse(BaseModel):
    slots: Dict[str, List[SlotItem]]

class EventTypeDetail(BaseModel):
    """Type definition for event type details returned by get_event_type_details_v2."""
    id: int
    slug: str
    title: str
    length: int
    description: Optional[str]
    locations: List[Location]
    requiresConfirmation: bool
    booking_url: str

class BookingSuccessResponse(BaseModel):
    """Type definition for successful booking response."""
    success: bool  # Always True
    data: Dict[str, Any]  # The actual booking data from Cal.com API

class BookingErrorResponse(BaseModel):
    """Type definition for failed booking response."""
    success: bool  # Always False
    error: str  # Error message

BookingResponse = Union[BookingSuccessResponse, BookingErrorResponse]

def get_event_type_details_v2(
    user_cal_username: str,
    event_type_slug: str
) -> Optional[EventTypeDetail]:
    """Fetches details for a specific event type by its slug using Cal.com API v2.
    
    Args:
        user_cal_username (str): The Cal.com username (e.g., 'username' from cal.com/username).
        event_type_slug (str): The slug of the event type to fetch (e.g., '30min').
    
    Returns:
        Optional[EventTypeDetail]: A dict of event type details if found, otherwise None.
    
    Raises:
        ValueError: If CAL_COM_API_KEY is not configured.
    """
    if not config.CAL_COM_API_KEY:
        raise ValueError("Error: CAL_COM_API_KEY is not configured for get_event_type_details_v2.")

    headers_v2: Dict[str, str] = {
        "Authorization": f"Bearer {config.CAL_COM_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(f"{CAL_API_V2_BASE_URL}/event-types", headers=headers_v2)
        response.raise_for_status()
        response_data: Dict[str, Any] = response.json()

        groups = response_data.get('data', {}).get('eventTypeGroups', [])
        if not groups or not isinstance(groups, list):
            print("Warning: Unexpected structure in V2 /event-types response.")
            return None

        event_types_list = groups[0].get('eventTypes', [])
        if not isinstance(event_types_list, list):
            print("Warning: 'eventTypes' field is missing or invalid.")
            return None

        for et in event_types_list:
            if et.get('slug') == event_type_slug:
                # Build basic detail dict
                detail: EventTypeDetail = {
                    "id": et.get('id'),
                    "slug": et.get('slug'),
                    "title": et.get('title'),
                    "length": et.get('lengthInMinutes') or et.get('length'),
                    "description": et.get('description'),
                    "locations": et.get('locations'),
                    "requiresConfirmation": et.get('requiresConfirmation'),
                    "booking_url": f"https://cal.com/{user_cal_username}/{et.get('slug')}"
                }
                return detail

        print(f"Event type with slug '{event_type_slug}' not found.")
        return None

    except requests.exceptions.RequestException as err:
        print(f"Request error (V2): {err}")
        return None


def get_available_slots_v1(
    event_type_id: str,
    days_to_check: int = 14,
    target_timezone: str = "UTC"
) -> List[str]:
    """Fetches available slots using Cal.com API v1 for a specified period.
    
    Args:
        event_type_id (str): The ID of the event type to fetch slots for.
        days_to_check (int, optional): Number of days to check for availability. Defaults to 14.
        target_timezone (str, optional): The timezone to return slots in. Defaults to "UTC".
    
    Returns:
        List[str]: A sorted list of available slot times in ISO8601 format.
    
    Raises:
        ValueError: If CAL_COM_API_KEY is not configured or event_type_id is missing.
    """
    if not config.CAL_COM_API_KEY:
        raise ValueError("Error: CAL_COM_API_KEY is not configured for get_event_type_details_v2.")

    api_key = config.CAL_COM_API_KEY

    if not event_type_id:
        raise ValueError("Error: event_type_id is required for get_available_slots_v1.")

    tomorrow_utc = (
        datetime.now(timezone.utc)
        .replace(hour=0, minute=0, second=0, microsecond=0)
        + timedelta(days=1)
    )
    end_date_utc = tomorrow_utc + timedelta(days=days_to_check - 1)

    start_time_iso: str = tomorrow_utc.isoformat()
    end_time_iso: str = (end_date_utc + timedelta(days=1)).isoformat()

    params: Dict[str, Any] = {
        "apiKey": api_key,
        "eventTypeId": event_type_id,
        "startTime": start_time_iso,
        "endTime": end_time_iso,
        "timeZone": target_timezone
    }

    slot_times: List[str] = []
    try:
        response = requests.get(f"{CAL_API_V1_BASE_URL}/slots", params=params)
        response.raise_for_status()
        data: SlotsResponse = response.json()

        slots_data = data.get('slots', {})
        if isinstance(slots_data, dict):
            for time_slots in slots_data.values():
                if isinstance(time_slots, list):
                    for slot in time_slots:
                        time_str = slot.get('time')
                        if isinstance(time_str, str):
                            slot_times.append(time_str)
        slot_times.sort()
        return slot_times

    except requests.exceptions.RequestException as err:
        print(f"Request error (V1): {err}")
        return []

# Aliases for backward compatibility
get_event_type_details = get_event_type_details_v2
get_available_slots = get_available_slots_v1

def create_booking(
    event_type_id: str,
    slot_time: str,
    user_email: str,
    user_name: Optional[str] = None,
    event_type_slug: Optional[str] = None,
    username: Optional[str] = None,
    time_zone: str = "Europe/Helsinki",
    language: str = "en",
    notes: Optional[str] = None
) -> BookingResponse:
    """Books a slot for the given event type and user using Cal.com v2 API.
    
    Args:
        event_type_id (str): The ID of the event type to book.
        slot_time (str): The ISO8601 UTC string for the slot time (e.g., '2024-08-13T09:00:00Z').
        user_email (str): Email address of the attendee.
        user_name (Optional[str], optional): Name of the attendee. Defaults to None.
        event_type_slug (Optional[str], optional): Slug of the event type. Defaults to None.
        username (Optional[str], optional): Cal.com username. Defaults to None.
        time_zone (str, optional): Timezone for the booking. Defaults to "Europe/Helsinki".
        language (str, optional): Language for the booking. Defaults to "en".
        notes (Optional[str], optional): Additional notes for the booking. Defaults to None.
    
    Returns:
        BookingResponse: Either a BookingSuccessResponse or BookingErrorResponse.
            On success: {"success": True, "data": booking_data}
            On failure: {"success": False, "error": error_message}
    
    Raises:
        ValueError: If CAL_COM_API_KEY is not configured.
    """
    if not config.CAL_COM_API_KEY:
        raise ValueError("Error: CAL_COM_API_KEY is not configured for get_event_type_details_v2.")

    headers = {
        "Content-Type": "application/json",
        "cal-api-version": "2024-08-13",
        "Authorization": f"Bearer {config.CAL_COM_API_KEY}"
    }
    payload = {
        "start": slot_time,  # Should be in UTC ISO format
        "attendee": {
            "name": user_name or user_email,
            "email": user_email,
            "timeZone": time_zone,
            "language": language
        },
        "eventTypeId": int(event_type_id)
    }
    if event_type_slug and username:
        payload["eventTypeSlug"] = event_type_slug
        payload["username"] = username
    if notes:
        payload["notes"] = notes
    try:
        response = requests.post(f"{CAL_API_V2_BASE_URL}/bookings", headers=headers, json=payload)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.RequestException as e:
        print(f"Booking error: {e}")
        return {"success": False, "error": str(e)}
