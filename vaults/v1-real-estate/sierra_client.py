import os
import requests
import json
import re
from typing import List, Dict, Union, Any

class SierraClient:
    """
    Python client for Sierra Interactive API, enforcing data schemas from Sierra Receptor Matrix.
    """
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key if api_key else os.getenv("SIERRA_API_KEY")
        self.base_url = base_url if base_url else os.getenv("SIERRA_BASE_URL")
        # Ensure base_url ends with a slash for consistent path joining
        if self.base_url and not self.base_url.endswith('/'):
            self.base_url += '/'

        if not self.api_key:
            raise ValueError("Sierra API Key not provided or found in environment variables.")
        if not self.base_url:
            raise ValueError("Sierra Base URL not provided or found in environment variables.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _validate_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> None:
        """Helper to validate data against a given schema."""
        for field, rules in schema.items():
            value = data.get(field)
            if value is None and rules.get("required", False): # Assuming 'required' can be added to the schema if needed
                raise ValueError(f"Validation Error: {field} is required. {rules.get('error', '')}")
            if value is not None:
                if not isinstance(value, rules["type"]):
                    raise TypeError(f"Validation Error: {field} must be of type {rules['type'].__name__}. {rules.get('error', '')}")
                if "validator" in rules and not rules["validator"](value):
                    raise ValueError(f"Validation Error: {rules.get('error', '')}")
        
        # Check for unexpected fields
        for field in data:
            if field not in schema:
                raise ValueError(f"Validation Error: Unexpected field '{field}' in data.")


    def _post(self, endpoint: str, data: Dict[str, Any]) -> requests.Response:
        """Internal POST request helper."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.post(url, headers=self.headers, data=json.dumps(data))
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"Request Error: {e}")
            raise

    # --- Schema Definitions (from sierra_receptor_matrix.md) ---
    PROPERTY_VIEW_SCHEMA = {
        "mls_number": {
            "type": int,
            "validator": lambda v: isinstance(v, int) and v > 0,
            "error": "MLS Number must be a positive integer. No strings, no formatting."
        },
        # Assuming only mls_number is sent for property views and it's required for tracking logic
        # Others can be added as needed based on specific Sierra API docs.
    }

    SAVED_SEARCH_SCHEMA = {
        "price_range": {
            "type": list,
            "validator": lambda v: (
                isinstance(v, list)
                and len(v) == 2
                and all(isinstance(p, int) and p >= 0 for p in v)
                and v[0] <= v[1]
            ),
            "error": "price_range must be [min_int, max_int] — integers only, no symbols, min <= max."
        },
        "polygon": {
            "type": list,
            "validator": lambda v: (
                isinstance(v, list)
                and len(v) >= 3
                and all(
                    isinstance(p, dict)
                    and isinstance(p.get("lat"), float)
                    and isinstance(p.get("lng"), float)
                    and -90 <= p["lat"] <= 90
                    and -180 <= p["lng"] <= 180
                    for p in v
                )
            ),
            "error": "polygon must be array of {lat: float, lng: float} objects. Minimum 3 points. Lat: -90 to 90. Lng: -180 to 180."
        },
        "property_type": {
            "type": str,
            "validator": lambda v: v in [
                "single_family", "condo", "townhouse", "multi_family",
                "land", "commercial", "mobile_home"
            ],
            "error": "property_type must be: single_family | condo | townhouse | multi_family | land | commercial | mobile_home"
        }
    }

    BEHAVIORAL_TRACKING_SCHEMA = {
        "lead_id": {
            "type": str,
            "validator": lambda v: isinstance(v, str) and len(v) > 0,
            "error": "Sierra lead_id is required."
        },
        "event_type": {
            "type": str,
            "validator": lambda v: v in ["property_view", "search_save", "inquiry", "login"],
            "error": "event_type must be: property_view | search_save | inquiry | login"
        },
        "timestamp": {
            "type": str,
            "validator": lambda v: bool(re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', v)),
            "error": "timestamp must be ISO 8601 UTC format."
        }
    }

    # --- API Methods ---
    def record_property_view(self, mls_number: int) -> Dict[str, Any]:
        """Records a property view event."""
        data = {"mls_number": mls_number}
        self._validate_schema(data, self.PROPERTY_VIEW_SCHEMA)
        # Placeholder for the actual API endpoint based on Sierra documentation
        # For now, it will return a mock success
        print(f"Mocking Sierra API call for Property View: {data}")
        # response = self._post("events/property_view", data)
        return {"status": "success", "message": "Property view recorded (mock)"}

    def record_saved_search(self, search_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Records a saved search event."""
        self._validate_schema(search_criteria, self.SAVED_SEARCH_SCHEMA)
        # Placeholder for the actual API endpoint
        print(f"Mocking Sierra API call for Saved Search: {search_criteria}")
        # response = self._post("events/saved_search", search_criteria)
        return {"status": "success", "message": "Saved search recorded (mock)"}

    def record_behavioral_event(self, lead_id: str, event_type: str, timestamp: str) -> Dict[str, Any]:
        """Records a general behavioral event."""
        data = {
            "lead_id": lead_id,
            "event_type": event_type,
            "timestamp": timestamp
        }
        self._validate_schema(data, self.BEHAVIORAL_TRACKING_SCHEMA)
        # Placeholder for the actual API endpoint
        print(f"Mocking Sierra API call for Behavioral Event: {data}")
        # response = self._post("events/behavioral_event", data)
        return {"status": "success", "message": "Behavioral event recorded (mock)"}

if __name__ == '__main__':
    # Example Usage (replace with actual key/url from environment or direct init)
    client = SierraClient(api_key="YOUR_SIERRA_API_KEY", base_url="https://api.sierrainteractive.com/v1") 

    # --- Property View ---
    try:
        print("\n--- Recording Property View ---")
        result = client.record_property_view(mls_number=123456789)
        print(result)
        # client.record_property_view(mls_number="invalid") # This would raise an error
    except (ValueError, TypeError) as e:
        print(f"Error: {e}")

    # --- Saved Search ---
    try:
        print("\n--- Recording Saved Search ---")
        search_data = {
            "price_range": [100000, 500000],
            "property_type": "single_family",
            "polygon": [
                {"lat": 34.0522, "lng": -118.2437},
                {"lat": 34.0000, "lng": -118.0000},
                {"lat": 34.1000, "lng": -118.1000}
            ]
        }
        result = client.record_saved_search(search_data)
        print(result)
        # client.record_saved_search({"property_type": "invalid_type"}) # This would raise an error
    except (ValueError, TypeError) as e:
        print(f"Error: {e}")

    # --- Behavioral Event ---
    try:
        print("\n--- Recording Behavioral Event ---")
        event_data = {
            "lead_id": "sierra_lead_abcd_1234",
            "event_type": "inquiry",
            "timestamp": "2026-05-23T10:30:00Z"
        }
        result = client.record_behavioral_event(**event_data)
        print(result)
        # client.record_behavioral_event(lead_id="", event_type="login", timestamp="invalid") # This would raise an error
    except (ValueError, TypeError) as e:
        print(f"Error: {e}")
