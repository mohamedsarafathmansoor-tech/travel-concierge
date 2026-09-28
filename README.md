# Travel Concierge 🧳✈️

![Travel Concierge Demo](demo.gif)

**Travel Concierge** is an intelligent, conversational AI travel assistant built using the Google Agent Development Kit (ADK) and Gemini models. It helps travelers research destination venues, check weather and time zones, convert currencies, calculate trip budgets via code execution, remember dietary allergies across sessions, and generate AI visual image and video previews of travel landmarks.

---

## 🌟 Implemented Features & Wired Tools

The following capabilities and tools are fully implemented in `app/` and registered with the agent:

### 🧠 Persistent Memory Bank
- **Allergy & Preference Tracking**: Automatically extracts, stores, and recalls traveler preferences, medical/dietary allergies, and budget limits across user sessions using `PreloadMemoryTool` and `LoadMemoryTool` with background memory generation callbacks.

### 🗄️ Google Cloud Firestore Database
- **Destination Catalog**: Queries and persists travel destinations and venue records in Cloud Firestore (`search_destinations`, `add_destination`).

### 🎨 Media Generation & Google Cloud Storage
- **Imagen 3 Preview Cards**: Generates AI image previews of landmarks using `imagen-3.0-generate-002`, uploads PNG media to Google Cloud Storage, and renders public HTTP image cards (`generate_destination_image`).
- **Gemini Omni Video Previews**: Generates short travel video previews using Google's `gemini-omni-flash-preview` model via the Interactions API, saving video artifacts and uploading MP4 media to Google Cloud Storage (`generate_destination_video`).

### 🖥️ A2UI (Agent-to-User Interface)
- **Structured UI Components**: Returns clean A2UI component trees (`Card`, `Column`, `Row`, `Text`, `Image`) formatted according to JSON schema definitions for a clean, visual chat experience.

### 🧮 Sandboxed Code Execution
- **Budget & Duration Math**: Executes Python code in an isolated sandbox (`get_code_executor`) to calculate complex trip budgets and duration math without arithmetic hallucinations.

### 🌐 Live External Tools & Services
- **Currency Conversion**: Real-time exchange rate calculations using the Frankfurter API (`convert_currency`).
- **Weather & Time**: Real-time local weather forecasts (`get_weather`) and time zone lookups (`get_current_time`).
- **Geocoding & Nearby Places**: Address geocoding (`geocode_address`) and local venue search (`find_nearby_places`).

---

## ☁️ Wired Google Cloud & Vertex AI Services

- **Vertex AI Reasoning Engine / Agent Runtime**: Hosts and runs the ADK agent.
- **Gemini 2.5 Flash (`gemini-2.5-flash`)**: Core LLM for multi-step reasoning, memory management, and tool calls.
- **Imagen 3 (`imagen-3.0-generate-002`)**: High-quality AI image generation.
- **Gemini Omni (`gemini-omni-flash-preview`)**: AI video generation.
- **Google Cloud Firestore**: NoSQL document database for destination catalog storage.
- **Google Cloud Storage**: Public bucket hosting generated preview images and video assets.

---

## 📋 Planned vs. Implemented

| Capability | Status |
| :--- | :--- |
| **Firestore Destination Catalog** | ✅ Implemented |
| **Persistent Memory Bank & Allergy Rules** | ✅ Implemented |
| **Currency Conversion (Live API)** | ✅ Implemented |
| **Weather & Geocoding** | ✅ Implemented |
| **AI Image Preview Cards (Imagen 3)** | ✅ Implemented |
| **AI Video Preview Cards (Gemini Omni)** | ✅ Implemented |
| **Code Sandbox (Itinerary Budgets)** | ✅ Implemented |
| **A2UI Structured Card Layouts** | ✅ Implemented |
| **Live Flight & Hotel Booking APIs** | ⏳ *Planned, not yet implemented* |

---

## 🚀 Setup & Local Execution

Follow these steps to run the agent locally or launch the Web UI:

### Prerequisites
- Python 3.11+
- Google Cloud Project with Vertex AI, Firestore, and Cloud Storage enabled
- Google Application Default Credentials (`gcloud auth application-default login`)

### 1. Installation
Clone the repository and install required dependencies:
```bash
pip install google-adk google-genai google-cloud-firestore google-cloud-storage fastapi uvicorn
```

### 2. Environment Configuration
Set required environment variables:
```bash
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export GOOGLE_CLOUD_REGION="us-east1"
```

### 3. Run the Agent

**Option A: ADK Web Playground**
```bash
adk web app/
```

**Option B: FastAPI Web Frontend**
```bash
python -m uvicorn frontend.main:app --reload --port 8080
```
