import requests
import config
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, TypedDict

CAL_API_V2_BASE_URL = "https://api.cal.com/v2"  # For event-types
CAL_API_V1_BASE_URL = "https://api.cal.com/v1"  # For slots

# --- TypedDict definitions matching Cal.com V2/Get an Event Type ---
class Location(TypedDict, total=False):
    type: str
    address: str
    public: bool

class BookingField(TypedDict):
    type: str
    label: str
    placeholder: str
    disableOnPrefill: bool
    isDefault: bool
    slug: str
    required: bool

class Recurrence(TypedDict):
    interval: int
    occurrences: int
    frequency: str  # e.g., 'daily', 'weekly', 'monthly', 'yearly'

class BookingWindowItem(TypedDict):
    type: str  # e.g., 'businessDays'
    value: int
    rolling: bool

class BookerLayouts(TypedDict):
    defaultLayout: str
    enabledLayouts: List[str]

class Color(TypedDict):
    lightThemeHex: str
    darkThemeHex: str

class SeatsConfig(TypedDict):
    seatsPerTimeSlot: int
    showAttendeeInfo: bool
    showAvailabilityCount: bool

class DestinationCalendar(TypedDict):
    integration: str
    externalId: str

class Host(TypedDict):
    userId: int
    mandatory: bool
    priority: str  # e.g., 'low', 'medium', 'high'
    name: str
    avatarUrl: str

class TeamInfo(TypedDict):
    id: int
    slug: str
    bannerUrl: str
    name: str
    logoUrl: str
    weekStart: str
    brandColor: str
    darkBrandColor: str
    theme: str

# --- TypedDict definitions for V1/slots response ---
class SlotItem(TypedDict):
    time: str

class SlotsResponse(TypedDict):
    slots: Dict[str, List[SlotItem]]

# Simplified return type for event details
EventTypeDetail = Dict[str, Any]


def get_event_type_details_v2(
    user_cal_username: str,
    event_type_slug: str
) -> Optional[Dict[str, Any]]:
    """Fetches details for a specific event type by its slug using Cal.com API v2.
    Args:
        user_cal_username (str): The Cal.com username (e.g., 'username' from cal.com/username).
        event_type_slug (str): The slug of the event type to fetch (e.g., '30min').
    Returns:
        Optional[Dict[str, Any]]: A dict of event type details if found, otherwise None.
    """
    if not config.CAL_COM_API_KEY:
        print("Error: CAL_COM_API_KEY is not configured for get_event_type_details_v2.")
        return None

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
                detail: Dict[str, Any] = {
                    "id": et.get('id'),
                    "slug": et.get('slug'),
                    "title": et.get('title'),
                    "length": et.get('lengthInMinutes') or et.get('length'),
                    "description": et.get('description'),
                    "locations": et.get('locations'),
                    "requiresConfirmation": et.get('requiresConfirmation'),
                    # Booking URL
                    "booking_url": f"https://cal.com/{user_cal_username}/{et.get('slug')}"
                }
                return detail

        print(f"Event type with slug '{event_type_slug}' not found.")
        return None

    except requests.exceptions.RequestException as err:
        print(f"Request error (V2): {err}")
        return None


def get_available_slots_v1(
    api_key: str,
    event_type_id: str,
    days_to_check: int = 14,
    target_timezone: str = "UTC"
) -> List[str]:
    """Fetches available slots using Cal.com API v1 for a specified period.

    Example response from API v1:
    {
      "slots": {
        "2024-04-13": [
          {"time": "2024-04-13T11:00:00+04:00"},
          {"time": "2024-04-13T12:00:00+04:00"},
          {"time": "2024-04-13T13:00:00+04:00"}
        ]
      }
    }
    """
    if not api_key:
        print("Error: Cal.com API key is required for get_available_slots_v1.")
        return []
    if not event_type_id:
        print("Error: event_type_id is required for get_available_slots_v1.")
        return []

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
    api_key: str,
    event_type_id: str,
    slot_time: str,  # Must be ISO8601 UTC string, not formatted
    user_email: str,
    user_name: str = None,
    event_type_slug: str = None,
    username: str = None,
    time_zone: str = "Europe/Helsinki",
    language: str = "en"
) -> Dict[str, Any]:
    """
    Books a slot for the given event type and user using Cal.com v2 API.
    slot_time must be the ISO8601 UTC string (e.g., '2024-08-13T09:00:00Z'), not the formatted string.
    Returns a dict with booking details or error.
    """
    url = "https://api.cal.com/v2/bookings"
    headers = {
        "Content-Type": "application/json",
        "cal-api-version": "2024-08-13",
        "Authorization": f"Bearer {api_key}"
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
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.RequestException as e:
        print(f"Booking error: {e}")
        return {"success": False, "error": str(e)}
