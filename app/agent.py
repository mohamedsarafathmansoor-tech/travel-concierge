# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import io
import json
import os
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
from google import genai
from google.cloud import firestore, storage

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.load_memory_tool import LoadMemoryTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from .a2ui_utils import a2ui_callback

# Hardcode project ID as a string to prevent issues on Agent Platform
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-58e1f44c73ce"
MEDIA_BUCKET_NAME = "travel-concierge-media-qwiklabs-gcp-02-58e1f44c73ce"
REASONING_ENGINE_ID = "473289178222690304"

memory_service = VertexAiMemoryBankService(
    project=FIRESTORE_PROJECT_ID,
    location="us-east1",
    agent_engine_id=REASONING_ENGINE_ID,
)


def get_maps_api_key() -> str:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key and os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("GOOGLE_MAPS_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return key or ""


def get_firestore_client():
    return firestore.Client(project=FIRESTORE_PROJECT_ID, database="(default)")


def get_code_executor():
    """Initializes AgentEngineSandboxCodeExecutor using deployment_metadata.json."""
    metadata_path = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
    if not os.path.exists(metadata_path):
        metadata_path = "deployment_metadata.json"

    sandbox_name = None
    engine_name = None
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                meta = json.load(f)
                sandbox_name = meta.get("sandbox_resource_name")
                engine_name = meta.get("remote_agent_runtime_id")
        except Exception:
            pass

    if sandbox_name:
        return AgentEngineSandboxCodeExecutor(sandbox_resource_name=sandbox_name)
    elif engine_name:
        return AgentEngineSandboxCodeExecutor(agent_engine_resource_name=engine_name)
    return None


async def generate_memories_callback(callback_context: CallbackContext):
    """Sends session events to Memory Bank so user details, preferences, and allergies are persisted across sessions."""
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


def search_destinations(city: str = "", category: str = "") -> str:
    """Searches travel destinations in the Firestore database by city or category.

    Args:
        city: Optional city name to filter destinations (e.g., 'San Francisco', 'New York', 'Paris', 'Tokyo').
        category: Optional category to filter destinations (e.g., 'Landmark', 'Park', 'Museum', 'Temple').

    Returns:
        A formatted list of matching travel destinations with details.
    """
    db = get_firestore_client()
    collection_ref = db.collection("destinations")
    docs = collection_ref.stream()

    results = []
    for doc in docs:
        data = doc.to_dict()
        doc_city = data.get("city", "").lower()
        doc_category = data.get("category", "").lower()

        match_city = not city or city.lower() in doc_city or doc_city in city.lower()
        match_category = not category or category.lower() in doc_category or doc_category in category.lower()

        if match_city and match_category:
            results.append({
                "id": doc.id,
                **data
            })

    if not results:
        return f"No destinations found matching city='{city}' and category='{category}'."

    output = f"Found {len(results)} destination(s):\n"
    for item in results:
        output += f"- {item.get('name')} in {item.get('city')}, {item.get('country')} ({item.get('category')}): {item.get('description')} [Rating: {item.get('rating')}, Price: {item.get('price_range')}]\n"
    return output


def add_destination(name: str, city: str, country: str, category: str, description: str, price_range: str = "$$", rating: float = 4.5) -> str:
    """Adds a new travel destination to the Firestore database.

    Args:
        name: Name of the destination/landmark/attraction (e.g. 'Eiffel Tower').
        city: City where the destination is located (e.g. 'Paris').
        country: Country where the destination is located (e.g. 'France').
        category: Category of attraction (e.g. 'Landmark', 'Museum', 'Park', 'Restaurant').
        description: A brief summary or highlight of the destination.
        price_range: Estimated cost category, such as 'Free', '$', '$$', '$$$'.
        rating: Customer/Visitor rating score from 1.0 to 5.0.

    Returns:
        A confirmation message after successfully saving to Firestore.
    """
    db = get_firestore_client()
    doc_id = f"{city.lower().replace(' ', '-')}-{name.lower().replace(' ', '-')}"
    data = {
        "name": name,
        "city": city,
        "country": country,
        "category": category,
        "description": description,
        "price_range": price_range,
        "rating": float(rating),
        "tags": [category.lower(), city.lower()],
    }
    db.collection("destinations").document(doc_id).set(data)
    return f"Successfully saved destination '{name}' ({city}, {country}) to database with ID '{doc_id}'."


def generate_destination_image(destination_name: str, prompt: str = "") -> str:
    """Generates a visual preview card image for a travel destination and uploads it to Cloud Storage.

    Args:
        destination_name: The name of the destination or landmark (e.g. 'Coit Tower', 'Central Park').
        prompt: Optional scene description or highlight prompt for the visual preview.

    Returns:
        The public Cloud Storage HTTP URL of the generated preview image.
    """
    img = Image.new("RGB", (600, 350), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, 600, 90], fill=(30, 58, 138))
    draw.rectangle([0, 85, 600, 90], fill=(59, 130, 246))

    draw.text((30, 25), "TRAVEL DESTINATION PREVIEW", fill=(147, 197, 253))
    draw.text((30, 120), f"Destination: {destination_name}", fill=(255, 255, 255))

    sub_text = prompt if prompt else f"Visual preview card for {destination_name}"
    draw.text((30, 170), f"Highlight: {sub_text[:65]}", fill=(203, 213, 225))
    draw.text((30, 290), "Generated by Travel Concierge AI", fill=(148, 163, 184))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    clean_name = destination_name.lower().replace(' ', '-').replace('/', '-')
    filename = f"previews/{clean_name}-{int(time.time())}.png"

    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(MEDIA_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_file(buffer, content_type="image/png")

    public_url = f"https://storage.googleapis.com/{MEDIA_BUCKET_NAME}/{filename}"
    return f"Generated preview image for '{destination_name}'. Public image URL: {public_url}"


def generate_destination_video(tool_context: ToolContext, destination_name: str, prompt: str = "") -> str:
    """Generates a short video preview for a travel destination using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Saves the generated video as an artifact in ToolContext and uploads the video bytes to public Cloud Storage.

    Args:
        destination_name: Name of the travel destination or landmark (e.g. 'Eiffel Tower', 'Tokyo Tower', 'Grand Canyon').
        prompt: Optional scene description or visual details for the video preview.

    Returns:
        A confirmation message containing the public Cloud Storage https URL of the generated video.
    """
    clean_name = destination_name.lower().replace(" ", "-").replace("/", "-")
    filename = f"videos/{clean_name}-{int(time.time())}.mp4"

    client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
    interaction_prompt = f"Generate a short travel video preview of {destination_name}"
    if prompt:
        interaction_prompt += f": {prompt}"

    interaction = client.interactions.create(
        model="gemini-omni-flash-preview",
        input=interaction_prompt,
        response_format={"video": {"duration": "3s"}}
    )

    out_vid = getattr(interaction, "output_video", None)
    if not out_vid or not getattr(out_vid, "data", None):
        return f"Failed to generate video for '{destination_name}'."

    raw_data = out_vid.data
    if isinstance(raw_data, str):
        video_bytes = base64.b64decode(raw_data)
    else:
        video_bytes = raw_data

    # (1) Save video with tool_context.save_artifact so it shows up in Playground Artifacts panel
    artifact_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
    try:
        tool_context.save_artifact(filename=filename, artifact=artifact_part)
    except Exception as e:
        print(f"Warning: save_artifact error: {e}")

    # (2) Upload video bytes to public Cloud Storage bucket
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(MEDIA_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type="video/mp4")

    public_url = f"https://storage.googleapis.com/{MEDIA_BUCKET_NAME}/{filename}"
    return f"Generated video preview for '{destination_name}'. Public video URL: {public_url}"


def convert_currency(from_currency: str = "USD", to_currency: str = "EUR", amount: float = 1.0) -> str:
    """Converts a monetary amount between currencies using live exchange rates from the Frankfurter public API.

    Args:
        from_currency: 3-letter currency code to convert from (e.g. 'USD', 'EUR', 'GBP', 'JPY', 'CAD').
        to_currency: 3-letter currency code to convert to (e.g. 'EUR', 'JPY', 'GBP', 'USD', 'AUD').
        amount: The monetary amount to convert.

    Returns:
        A string with the calculated converted currency amount and live exchange rate date.
    """
    from_curr = from_currency.strip().upper()
    to_curr = to_currency.strip().upper()

    api_key = os.environ.get("CURRENCY_API_KEY", "")

    url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_curr}&to={to_curr}"
    headers = {"User-Agent": "Mozilla/5.0 TravelConcierge/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rate = data.get("rates", {}).get(to_curr)
            if rate is not None:
                return f"{amount:.2f} {from_curr} = {rate:.2f} {to_curr} (Live Rate Date: {data.get('date')})"
            return f"Could not find live rate for converting {from_curr} to {to_curr}."
    except Exception as e:
        return f"Error fetching exchange rates from {from_curr} to {to_curr}: {str(e)}"


def geocode_address(address: str) -> str:
    """Converts a physical address or landmark location name into geographic latitude and longitude coordinates using Google Geocoding API.

    Args:
        address: The address, city, or landmark string to geocode (e.g., '1600 Amphitheatre Pkwy, Mountain View, CA' or 'Times Square New York').

    Returns:
        A string containing the formatted address and latitude/longitude coordinates.
    """
    key = get_maps_api_key()
    if not key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not configured."

    encoded_address = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={key}"
    req = urllib.request.Request(url, headers={"User-Agent": "TravelConcierge/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "OK" and data.get("results"):
                first_result = data["results"][0]
                formatted_addr = first_result.get("formatted_address")
                location = first_result.get("geometry", {}).get("location", {})
                lat = location.get("lat")
                lng = location.get("lng")
                return f"Geocoding Result for '{address}':\n- Address: {formatted_addr}\n- Location: Latitude {lat}, Longitude {lng}"
            return f"Geocoding failed for '{address}'. Status: {data.get('status')}."
    except Exception as e:
        return f"Error connecting to Geocoding API: {str(e)}"


def find_nearby_places(latitude: float, longitude: float, place_type: str = "restaurant", radius_meters: float = 1000.0) -> str:
    """Finds nearby places of a specified type near given coordinates using the Places API (New).

    Args:
        latitude: Geographic latitude coordinate (e.g., 40.7579747).
        longitude: Geographic longitude coordinate (e.g., -73.9855426).
        place_type: The type of place to search for (e.g. 'restaurant', 'tourist_attraction', 'museum', 'hotel', 'park').
        radius_meters: Search radius in meters (default 1000.0).

    Returns:
        A formatted list of nearby places with key fields (name, formatted address, location coordinates, rating).
    """
    key = get_maps_api_key()
    if not key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not configured."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.rating,places.types",
        "User-Agent": "TravelConcierge/1.0"
    }

    body = {
        "includedTypes": [place_type.lower().strip()],
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": float(latitude),
                    "longitude": float(longitude)
                },
                "radius": float(radius_meters)
            }
        }
    }

    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            places = data.get("places", [])
            if not places:
                return f"No nearby places of type '{place_type}' found within {radius_meters}m of ({latitude}, {longitude})."

            output = f"Found {len(places)} nearby '{place_type}' place(s):\n"
            for item in places[:5]:
                display_name = item.get("displayName", {}).get("text", "Unknown Place")
                addr = item.get("formattedAddress", "N/A")
                loc = item.get("location", {})
                lat_val = loc.get("latitude")
                lng_val = loc.get("longitude")
                rating = item.get("rating", "N/A")
                output += f"- Name: {display_name}\n  Address: {addr}\n  Location: ({lat_val}, {lng_val})\n  Rating: {rating}\n"
            return output
    except Exception as e:
        return f"Error connecting to Places API (New): {str(e)}"


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Travel Concierge, a helpful AI travel assistant designed to provide accurate travel info, "
        "calculate itinerary budgets via sandboxed code execution, geocode addresses, search nearby places, "
        "search destinations in Firestore, convert currencies, save new destinations, generate image preview cards, "
        "and generate short travel video previews using Google's Omni model (gemini-omni-flash-preview) uploaded to Cloud Storage."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects.\n\n"
        "IMPORTANT MEMORY & ALLERGY RULES:\n"
        "1. ALWAYS pay strict attention to user dietary preferences, food allergies, medical allergies, or environmental allergies "
        "mentioned by the user in conversation.\n"
        "2. Save and remember all user allergies in memory so they are preserved across sessions.\n"
        "3. When recommending restaurants, food, activities, or travel destinations, ALWAYS check preloaded memories and "
        "use load_memory when needed to ensure recommendations strictly avoid any items the user is allergic to."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=get_code_executor(),
    instruction=instruction,
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
    tools=[
        get_weather,
        get_current_time,
        search_destinations,
        add_destination,
        generate_destination_image,
        generate_destination_video,
        convert_currency,
        geocode_address,
        find_nearby_places,
        PreloadMemoryTool(),
        LoadMemoryTool(),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
