import os
import base64
import datetime
from fub_api_client import FUBAPIClient
from dotenv import load_dotenv

# Helper function for market insights (placeholder)
def market_insight(tags):
    # This will be replaced by actual API calls to CloudCMA/Homebeat later.
    # For now, simulate localized market knowledge based on available tags.
    insights = []

    # General lead status
    if "Arrived in New" in tags:
        insights.append("Newly arrived lead, prime for immediate engagement.")
    if "First Call Never Made" in tags:
        insights.append("No initial contact made. High priority for outreach.")

    # Geographic interest from tags (towns/zips)
    if any(tag in tags for tag in ["Red Hook", "12571", "Extension Red Hook", "Poughkeepsie"]):
        insights.append(
            "📍 **Red Hook/Poughkeepsie Market Update**: Seeing strong buyer activity with limited inventory. Focus on new listings quickly and highlight unique features of available homes."
        )
    elif any(tag in tags for tag in ["Beacon", "12404"]):
        insights.append(
            "📍 **Beacon Market Update**: Steady demand, especially for waterfront or renovated properties. Emphasize lifestyle benefits."
        )
    elif any(tag.isdigit() and len(tag) == 5 for tag in tags): # Generic zip code
        zip_tags = [tag for tag in tags if tag.isdigit() and len(tag) == 5]
        for zip_tag in zip_tags:
            insights.append(f"📍 **Market Pulse for {zip_tag}**: Properties here are moving fast. Be ready to act quickly.")

    # Property type interest (e.g., Seller tag implies selling)
    if "Seller" in tags:
        insights.append("Potential seller. Research recent comparable sales in their area to prepare for a listing presentation.")
    if "Buyer" in tags:
        insights.append("Buyer looking for properties. Understand specific needs (beds, baths, price) to align with inventory.")


    # General call to action if no specific insights
    if not insights:
        insights.append("Check for recent market trends and local events that might interest the client.")

    return " ".join(insights)


class FUBGuidanceGenerator:
    def __init__(self):
        self.fub_client = FUBAPIClient()
        self.audio_dir = "/root/omni-anchor/resources/audio"
        os.makedirs(self.audio_dir, exist_ok=True)

        self.receptor_matrix_rules = [
            {
                "name": "new_lead_no_contact",
                "condition": lambda data: data.get("stage") == "Lead" and "First Call Never Made" in data.get("tags", []),
                "template": (
                    "🔔 **URGENT**: New Lead - No First Call Made!\n"
                    "Initiate contact NOW. Call {phone} and email {email} (if available).\n"
                    "Focus on learning their core needs and timeline.\n"
                    "Market Intel: {market_insight}"
                )
            },
            {
                "name": "high_engagement_lead",
                "condition": lambda data: data.get("websiteVisits", 0) > 0 and data.get("stage") == "Lead",
                "template": (
                    "🚀 **High Engagement Detected for {first_name}!**\n"
                    "Review recent website activity (properties viewed, searches) for hints.\n"
                    "Reach out with highly personalized insights for {market_area_interest}.\n"
                    "Suggest: \"I noticed you were browsing properties – anything specific catch your eye?\".\n"
                    "Market Intel: {market_insight}"
                )
            },
            {
                "name": "default_guidance",
                "condition": lambda data: True, # Always applies if no other rule matches
                "template": (
                    "💡 Standard Lead Review for {full_name}.\n"
                    "Current Stage: {stage}. Assigned: {assigned_to}.\n"
                    "Ensure all basic contact info is validated.\n"
                    "Market Pulse: Keep an eye on {market_area_interest} for new opportunities.\n"
                    "Market Intel: {market_insight}"
                )
            }
        ]

    def get_person_guidance_text(self, person_id):
        try:
            person_data = self.fub_client.get_person(person_id)
            generated_text_guidance = self._generate_text_guidance(person_data)
            return {"person_data": person_data, "text_guidance": generated_text_guidance}
        except Exception as e:
            return { "error": f"Failed to get guidance for person {person_id}: {e}" }

    def _generate_text_guidance(self, person_data):
        for rule in self.receptor_matrix_rules:
            if rule["condition"](person_data):
                # Prepare data for template formatting
                formatted_data = {
                    "first_name": person_data.get("firstName", ""),
                    "full_name": person_data.get("name", ""),
                    "stage": person_data.get("stage", ""),
                    "assigned_to": person_data.get("assignedTo", ""),
                    "email": person_data["emails"][0]["value"] if person_data.get("emails") else "N/A",
                    "phone": person_data["phones"][0]["value"] if person_data.get("phones") else "N/A",
                    "market_insight": market_insight(person_data.get("tags", [])),
                    "market_area_interest": ", ".join([t for t in person_data.get("tags", []) if t.isdigit() or t in ["Red Hook", "Beacon", "Poughkeepsie", "12571", "12404"]]) or "their areas of interest"
                }
                return rule["template"].format(**formatted_data)

        return f"No specific guidance triggered for {person_data.get('name', '')}. Basic profile data: {person_data}"


if __name__ == "__main__":
    # Ensure .env is loaded for standalone testing
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env")) # Only needed for standalone test

    print("Loading FUB API Key...")
    api_key_status = "Found" if os.getenv("FUB_API_KEY") else "NOT Found"
    print(f"FUB_API_KEY status: {api_key_status}")

    generator = FUBGuidanceGenerator()

    test_person_ids = [90251, 90250, 90249]

    for person_id in test_person_ids:
        guidance_result = generator.get_person_guidance_text(person_id)

        if "error" in guidance_result:
            print(f"\n--- Guidance for Person ID {person_id} ({person_id}) ---")
            print(guidance_result["error"])
        else:
            text_guidance = guidance_result["text_guidance"]
            person_name = guidance_result["person_data"].get("name", str(person_id))
            
            print(f"\n--- Guidance for Person ID {person_id} ({person_name}) ---")
            print(text_guidance)

            # --- EXTERNALIZED AUDIO GENERATION AND FUB UPDATE ---
            # This part will be executed via execute_code in the agent's next turn, 
            # not directly here, to ensure hermes_tools access.
            # The print statement below simulates what would be passed to execute_code
            audio_file_name = f"{person_id}-guidance.ogg"
            audio_file_path = os.path.join(generator.audio_dir, audio_file_name)
            audio_url = f"https://widget.hvsold.com/resources/audio/{audio_file_name}"

            # Simulate response from hermes_tools.default_api.text_to_speech
            # For actual execution, this part needs to be outside this script's direct run
            # tts_response = default_api.text_to_speech(text=text_guidance, output_path=audio_file_path)

            # This is the full payload for the custom field update
            combined_guidance_for_fub = f"Text Guidance:\n{text_guidance}\n\nAudio Overview:\n{audio_url}"
            custom_fields_to_update = {
                "customOmniRelevancyTier": combined_guidance_for_fub
            }
            # print(f"*** FUB Custom Field Update Payload for {person_id}: {custom_fields_to_update}")
            # print(f"*** Simulated Audio Gen Path: {audio_file_path}")
            # This call too needs to be outside in the agent's loop that has access to hermes_tools
            # generator.fub_client.update_person_custom_fields(person_id, custom_fields_to_update)

    # Example with an unknown person ID
    unknown_person_id = 9999999
    guidance_unknown = generator.get_person_guidance_text(unknown_person_id)
    print(f"\n--- Guidance for Person ID {unknown_person_id} ---")
    print(guidance_unknown)
