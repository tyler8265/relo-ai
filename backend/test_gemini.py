import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY_1"))

def get_rent(city: str, bedrooms: int) -> dict:
    """Returns average monthly rent for a city."""
    return {"city": city, "bedrooms": bedrooms, "rent": 2400}  # hardcoded for now

resp = client.models.generate_content(
    model="gemini-2.5-flash",  # check AI Studio for the current flash model name
    contents="What would a 1-bedroom cost me in Seattle?",
    config=types.GenerateContentConfig(tools=[get_rent]),
)
print(resp.text)
