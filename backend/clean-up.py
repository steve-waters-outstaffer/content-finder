from google.cloud import firestore

client = firestore.Client()
collection_ref = client.collection('voc_discovery_processed_posts')

# Delete all documents in collection
batch = client.batch()
docs = collection_ref.stream()
count = 0
for doc in docs:
    batch.delete(doc.reference)
    count += 1
    if count >= 500:  # Firestore batch limit
        batch.commit()
        batch = client.batch()
        count = 0
batch.commit()

print("Collection deleted")