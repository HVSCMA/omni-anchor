import os
import requests
import base64
import datetime

class FUBAPIClient:
    def __init__(self):
        self.api_key = os.getenv("FUB_API_KEY")
        if not self.api_key:
            raise ValueError("FUB_API_KEY environment variable not set.")
        self.base_url = "https://api.followupboss.com/v1"
        encoded_auth = base64.b64encode(f"{self.api_key}:".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json"
        }

    def get_person(self, person_id):
        url = f"{self.base_url}/people/{person_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()

    def get_people(self, params=None):
        url = f"{self.base_url}/people"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def create_note(self, person_id: int, note_body: str, subject: str | None = None, is_html: bool = False):
        url = f"{self.base_url}/notes"
        payload = {
            "personId": person_id,
            "body": note_body
        }
        if subject:
            payload["subject"] = subject
        if is_html:
            payload["isHtml"] = is_html

        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()

    def get_custom_fields(self):
        url = f"{self.base_url}/customFields"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def update_person_custom_fields(self, person_id: int, custom_fields_data: dict):
        url = f"{self.base_url}/people/{person_id}"
        # Send the custom_fields_data directly as the payload, no wrapping 'customFields' key
        payload = custom_fields_data
        response = requests.put(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    # Ensure FUB_API_KEY is loaded for standalone testing
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

    try:
        client = FUBAPIClient()

        print("--- Testing FUB API Client ---")

        # Test fetching custom fields
        custom_fields_response = client.get_custom_fields()
        print(f"Custom Fields: {custom_fields_response.get('customfields', [])[:2]}...") # Print first 2 for brevity

        # Test fetching a list of people
        all_people_response = client.get_people(params={"limit": 1})
        #print(f"First person: {all_people_response}")
        print(f"First person: {all_people_response.get('people', [])[0]['name'] if all_people_response.get('people') else 'N/A'}")

        # Test updating custom field for the first person
        if all_people_response and all_people_response['people']:
            first_person_id = all_people_response['people'][0]['id']
            timestamp = datetime.datetime.now().isoformat()
            custom_fields_to_update = {
                "customOmniTriggerTimestamp": f"Test {timestamp}"
            }
            updated_person_response = client.update_person_custom_fields(first_person_id, custom_fields_to_update)
            print(f"Successfully updated custom fields for person {first_person_id}. Response: {updated_person_response.get('id', 'N/A')}\n")
        else:
            print("No people found to update custom fields for.")

        # Test creating a note for the first person
        if all_people_response and all_people_response['people']:
            first_person_id = all_people_response['people'][0]['id']
            note_message = f"Test note from Hermes with confirmed payload at {os.environ.get('HOSTNAME', 'unknown')} - {datetime.datetime.now().isoformat()}"
            subject_line = "Hermes Automated Note Test"
            note_response = client.create_note(first_person_id, note_message, subject=subject_line, is_html=False)
            print(f"Successfully created note for person {first_person_id}: {note_response}")
        else:
            print("No people found to create a note for.")


    except ValueError as e:
        print(f"Configuration Error: {e}")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
