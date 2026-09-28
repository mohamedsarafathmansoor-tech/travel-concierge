import time
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-02-58e1f44c73ce"

SEED_DESTINATIONS = [
    {
        "id": "sf-coit-tower",
        "name": "Coit Tower",
        "city": "San Francisco",
        "country": "USA",
        "category": "Landmark",
        "description": "Art Deco tower with 360-degree views of the San Francisco Bay area and historic murals.",
        "rating": 4.6,
        "price_range": "$$",
        "tags": ["views", "history", "art"],
    },
    {
        "id": "ny-central-park",
        "name": "Central Park",
        "city": "New York",
        "country": "USA",
        "category": "Park",
        "description": "Iconic urban park offering walking paths, boat rides, zoo, and scenic greenery in Manhattan.",
        "rating": 4.8,
        "price_range": "Free",
        "tags": ["nature", "outdoors", "iconic"],
    },
    {
        "id": "paris-louvre",
        "name": "Louvre Museum",
        "city": "Paris",
        "country": "France",
        "category": "Museum",
        "description": "World's largest art museum and historic monument housing masterpieces like the Mona Lisa.",
        "rating": 4.7,
        "price_range": "$$$",
        "tags": ["art", "museum", "culture"],
    },
    {
        "id": "tokyo-sensoji",
        "name": "Sensō-ji Temple",
        "city": "Tokyo",
        "country": "Japan",
        "category": "Temple",
        "description": "Ancient Buddhist temple located in Asakusa, Tokyo's oldest temple filled with culture and shopping stalls.",
        "rating": 4.7,
        "price_range": "Free",
        "tags": ["culture", "temple", "history"],
    },
]


def seed_database():
    print(f"Connecting to Firestore with project ID: '{PROJECT_ID}'...")
    db = firestore.Client(project=PROJECT_ID, database="(default)")
    collection_ref = db.collection("destinations")

    for item in SEED_DESTINATIONS:
        doc_id = item["id"]
        data = {k: v for k, v in item.items() if k != "id"}
        success = False
        for attempt in range(3):
            try:
                collection_ref.document(doc_id).set(data)
                print(f"  Seeded destination: {item['name']} ({doc_id})")
                success = True
                break
            except Exception as e:
                print(f"  Attempt {attempt + 1} failed for {doc_id}: {e}")
                time.sleep(1)
        if not success:
            print(f"  Failed to seed {doc_id} after retries.")

    print("Firestore seeding completed!")


if __name__ == "__main__":
    seed_database()
