from youtube_transcript_api import YouTubeTranscriptApi
import re

def extract_video_id(url):
    match = re.search(r"v=([^&]+)", url)
    return match.group(1) if match else None

def get_transcript(url):
    video_id = extract_video_id(url)
    if not video_id:
        return "Invalid YouTube URL"

    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([t['text'] for t in transcript])
    except Exception as e:
        return f"Error fetching transcript: {str(e)}"
