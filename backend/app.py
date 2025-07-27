import os
import re
import json
import requests
from dotenv import load_dotenv

from flask import Flask, request, jsonify
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(__name__)
CORS(app)

# Load YouTube Data API key
YT_API_KEY = os.getenv("YT_API_KEY")

# Gemini API configuration
# Leave this as an empty string. The Canvas environment is expected to provide it at runtime.
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") # Reverted to empty string as per instructions

# Extract video ID from various YouTube URL formats
def extract_video_id(url):
    patterns = [
        r"v=([0-9A-Za-z_-]{11})",
        r"youtu\.be/([0-9A-Za-z_-]{11})",
        r"embed/([0-9A-Za-z_-]{11})"
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


# Fetch transcript or fallback to Hindi if English fails
def get_transcript_fallback(video_id):
    try:
        # Try to get English transcript first
        return YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
    except TranscriptsDisabled:
        # If transcripts are disabled, re-raise the specific exception
        raise
    except Exception:
        # If English fails for other reasons, try Hindi
        try:
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            return transcripts.find_transcript(['hi']).fetch()
        except Exception as e:
            # If Hindi also fails, re-raise the original exception
            raise e


# Trim transcript to 4000 characters (Gemini API limit)
def trim_to_char_limit(text, max_chars=4000):
    return text if len(text) <= max_chars else text[:max_chars]


# Fetch video metadata from YouTube Data API
def fetch_video_info(video_id):
    if not YT_API_KEY:
        print("YouTube Data API key not found. Skipping video info fetch.")
        return {}
    try:
        youtube = build("youtube", "v3", developerKey=YT_API_KEY)
        resp = youtube.videos().list(
            part="snippet",
            id=video_id
        ).execute()
        items = resp.get("items", [])
        if not items:
            print(f"No video info found for ID: {video_id}")
            return {}
        snip = items[0]["snippet"]
        return {
            "title": snip.get("title"),
            "channel": snip.get("channelTitle"),
            "publishedAt": snip.get("publishedAt")
        }
    except Exception as e:
        print(f"Error fetching video info: {e}")
        return {}


# Generate summary using Gemini API (synchronous version for Flask)
def generate_summary_with_gemini(transcript_text):
    prompt = (
        "You are a helpful assistant that summarizes YouTube transcripts.\n\n"
        "Transcript:\n"
        f"{transcript_text}\n\n"
        "Provide a concise summary and then 3–5 bullet‑point key points."
    )

    chat_history = []
    # FIX: Changed .push() to .append() for Python lists
    chat_history.append({"role": "user", "parts": [{"text": prompt}]})
    payload = {"contents": chat_history}

    # API URL for gemini-2.0-flash
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    print(f"Attempting to call Gemini API at: {api_url}") # Debugging print

    try:
        response = requests.post(
            api_url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(payload)
        )
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        result = response.json()

        if result.get("candidates") and len(result["candidates"]) > 0 and \
           result["candidates"][0].get("content") and \
           result["candidates"][0]["content"].get("parts") and \
           len(result["candidates"][0]["content"]["parts"]) > 0:
            text = result["candidates"][0]["content"].get("parts")[0].get("text")
            return text
        else:
            print("Unexpected response structure from Gemini API:", result)
            return "Failed to generate summary: Unexpected API response."
    except requests.exceptions.RequestException as e:
        print(f"Error calling Gemini API: {e}")
        # Include response text if available for more detailed debugging
        if e.response is not None:
            print(f"API Response Status Code: {e.response.status_code}")
            print(f"API Response Content: {e.response.text}")
        return f"Failed to generate summary: API call error - {e}"
    except Exception as e:
        print(f"An unexpected error occurred during Gemini API call: {e}")
        return f"Failed to generate summary: {e}"


# API endpoint to summarize YouTube video transcript
@app.route("/api/summarize", methods=["POST"])
def summarize_video():
    data = request.get_json() or {}
    url = data.get("url")

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    vid = extract_video_id(url)
    if not vid:
        return jsonify({"error": "Invalid YouTube URL"}), 400

    try:
        transcript = get_transcript_fallback(vid)
        texts = [entry.get("text", "") if isinstance(entry, dict) else getattr(entry, "text", "") for entry in transcript]
        full_text = " ".join(texts)
        trimmed = trim_to_char_limit(full_text)

        # Generate Gemini summary
        out = generate_summary_with_gemini(trimmed)

        # Handle potential error messages from generate_summary_with_gemini
        if out.startswith("Failed to generate summary:"):
            return jsonify({"error": out}), 500

        lines = out.split("\n")
        summary_lines, bullets = [], []
        hit_bullets = False

        for line in lines:
            if re.match(r"^[\-\u2022]\s+", line):
                hit_bullets = True
            if hit_bullets:
                bullets.append(line.lstrip("-• ").strip())
            else:
                summary_lines.append(line)

        summary = " ".join(summary_lines).strip()
        word_count = len(trimmed.split())
        reading_time = round(word_count / 200, 1)

        video_info = fetch_video_info(vid)

        return jsonify({
            "transcript": trimmed,
            "summary": summary,
            "keyPoints": [b for b in bullets if b],
            "tags": ["AI", "Gemini", "YouTube", "Summary"],
            "wordCount": word_count,
            "readingTime": reading_time,
            "videoInfo": video_info
        })

    except TranscriptsDisabled:
        return jsonify({"error": "Transcript disabled for this video"}), 400
    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": f"Failed to generate summary: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)
