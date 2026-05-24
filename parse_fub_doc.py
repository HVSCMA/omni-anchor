from bs4 import BeautifulSoup
import json
import re
import os

def extract_json_payload(html_file_path):
    try:
        with open(html_file_path, 'r') as f:
            html_content = f.read()
    except FileNotFoundError:
        return "Error: HTML file not found."

    soup = BeautifulSoup(html_content, 'html.parser')

    # Strategy: Find any element containing the text 'POST /v1/notes', then look for related code blocks.
    # Readme.io documentation is dynamically rendered and structured.

    target_element = None
    # First, try to find a link that matches the endpoint, as seen in the sidebar links
    target_link = soup.find('a', href='/reference/notes-post')
    if target_link:
        # On Readme.io, the actual API definition is typically near an h2/h3 or a specific 'method' element.
        # We need to find the context where the example body is. It's not a simple direct parent/sibling.
        # This often involves looking for an ancestor that contains the entire API method block.
        # The 'Example Request Body' is what we are after.

        # More robust search within the main content area for any text element that implies 'POST /v1/notes'
        # and then traversing up/down to find the code example.

        # Look for the code example heading text
        example_heading = soup.find(lambda tag: tag.name in ['h3', 'h4', 'h5'] and 
                                           re.search(r'Example Request Body(?!: response)', tag.text, re.IGNORECASE))

        if example_heading:
            # The JSON example is usually in a <pre><code> block right after this heading
            json_code_block = example_heading.find_next_sibling(attrs={'data-lang': 'json'})
            if json_code_block:
                # sometimes it's nested one more level
                json_found_text = json_code_block.text
                # Look for { characters to confirm it's within the JSON structure
                if '{' in json_found_text and '}' in json_found_text:
                    try:
                        # Clean up surrounding whitespace and ensure it's valid JSON
                        cleaned_json = re.sub(r'\s*<!--.*?-->\s*', '', json_found_text, flags=re.DOTALL) # Remove comments
                        json_object = json.loads(cleaned_json.strip())
                        return json_object
                    except json.JSONDecodeError as e:
                        return f"Found JSON-like text, but failed to parse: {json_found_text} - Error: {e}"

    # If the above highly specific search fails, try a broader search for JSON code blocks.
    for code_block in soup.find_all('code', class_=re.compile(r'language-json|lang-json')):
        # Heuristic: if a JSON block contains person_id, text, note, content, or entityType and entityId
        # it's highly likely the request body for notes creation.
        if re.search(r'"person_id"|"personId"|"entityType"|"entityId"|"text"|"note"|"content"|"description"', 
                     code_block.text, re.IGNORECASE):
            json_example_found = code_block.text
            # This is a fallback, less precise than finding the exact heading
            try:
                json_start = json_example_found.find('{')
                json_end = json_example_found.rfind('}')
                if json_start != -1 and json_end != -1 and json_end > json_start:
                    clean_json_string = json_example_found[json_start : json_end + 1 ]
                    return json.loads(clean_json_string)
                else:
                    return f"Found JSON-like text (fallback), but could not isolate valid JSON: {json_example_found}"
            except json.JSONDecodeError as e:
                return f"Found JSON-like text (fallback), but failed to parse: {json_example_found} - Error: {e}"

    return "Error: Could not find a suitable JSON example payload in the HTML."


html_file = "fub_notes_api_doc.html"
payload = extract_json_payload(html_file)
print(payload)
