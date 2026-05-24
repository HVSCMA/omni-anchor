
import os
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

@app.route('/', methods=['GET', 'POST'])
def google_assistant_webhook():
    """
    Handles incoming POST requests from Google Assistant for fulfillment.
    """
    req = request.get_json(silent=True, force=True)
    print(f"Received Google Assistant request: {json.dumps(req, indent=2)}")

    # Extract user query
    user_query = ""
    try:
        user_query = req.get('handler').get('name') if req.get('handler') else req['inputs'][0]['rawInputs'][0]['query']
        if not user_query:
            user_query = "Could not extract query." # Fallback for unexpected structure
    except (KeyError, TypeError) as e:
        print(f"Error extracting user query: {e}")
        user_query = "Could not extract query due to an error."

    # Placeholder for OMNI-ANCHOR processing logic
    # In a real scenario, this would involve:
    # 1. Calling the primary LLM (Gemini 2.5 Flash) with the user_query
    # 2. Orchestrating tools (fub_guidance_generator, etc.)
    # 3. Potentially escalating to Oracle Agent (Gemini 1.5 Pro) if needed
    # 4. Forming a coherent response

    # For now, a simple echo response
    response_text = f"You said: {user_query}. This is a placeholder response from OMNI-ANCHOR's Google Assistant webhook."

    # Construct the fulfillment response for Google Assistant
    # This structure is based on the Actions on Google fulfillment protocol for simple responses
    fulfillment_response = {
        "prompt": {
            "firstSimple": {
                "speech": response_text,
                "text": response_text
            }
        }
    }

    print(f"Sending Google Assistant response: {json.dumps(fulfillment_response, indent=2)}")
    return jsonify(fulfillment_response)

if __name__ == '__main__':
    # For local development purposes, this might run on port 5000
    # In production, it will be run by Gunicorn/nginx or similar
    app.run(host='0.0.0.0', port=5001) # Using 5001 to avoid potential conflicts with local dev environments
