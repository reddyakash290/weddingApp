import os
import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from google.cloud import storage
from dotenv import load_dotenv

# 1. Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app)

# 2. Configuration from .env or Environment Variables
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
EXPIRATION_MINS = int(os.getenv("LINK_EXPIRATION", 60))

# 3. Route to serve your Website (index.html)
@app.route('/')
def index():
    """Serves the frontend HTML file."""
    return send_from_directory('.', 'index.html')

# 4. Helper function for Signed URLs
def generate_signed_url(blob_name):
    """Generates a temporary, secure link for a private GCS file using IAM signing."""
    try:
        # Get the email from the Cloud Run Environment Variable
        service_account_email = os.environ.get("SERVICE_ACCOUNT_EMAIL")
        
        if not service_account_email:
            print("Error: SERVICE_ACCOUNT_EMAIL environment variable is not set.")
            return None

        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)

        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=EXPIRATION_MINS),
            method="GET",
            # This line tells the library to use the IAM API instead of a local key file
            service_account_email=service_account_email
        )
        return url
    except Exception as e:
        print(f"Error generating signed URL: {e}")
        return None

# 5. API Route to fetch photos for a specific event
@app.route('/gallery')
def get_gallery():
    """Returns a list of signed photo URLs for a given event ID."""
    event_id = request.args.get('event')
    
    if not event_id:
        return jsonify({"error": "No event ID provided in URL"}), 400

    try:
        storage_client = storage.Client()
        # Lists all files in the 'folder' named after the event_id
        # Example: gs://your-bucket/wedding123/photo.jpg
        blobs = storage_client.list_blobs(BUCKET_NAME, prefix=f"{event_id}/")

        urls = []
        for b in blobs:
            # Ignore the 'folder' object itself, only get files
            if not b.name.endswith('/'):
                signed_url = generate_signed_url(b.name)
                if signed_url:
                    urls.append(signed_url)
        
        return jsonify({
            "event": event_id,
            "total_photos": len(urls),
            "photos": urls
        })
    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

if __name__ == '__main__':
    # Cloud Run provides the PORT environment variable
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)