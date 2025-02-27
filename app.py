import streamlit as st
st.set_page_config(page_title="YouTube Audio & Whisper Transcript", page_icon="🎵")

import os
import subprocess
import base64
import re
from pathlib import Path
import time
import json
import requests  # Needed for calling the YouTube Data API

# --- Optional: Attempt to import whisper (for local processing) ---
try:
    import whisper
except ModuleNotFoundError:
    print("Installing openai-whisper package...")
    subprocess.check_call(["pip", "install", "openai-whisper", "--quiet"])
    import whisper

# --- Load API keys from st.secrets if available ---
@st.cache_resource
def get_api_keys():
    config = {"openai_api_key": None, "youtube_api_key": None}
    try:
        if "OPENAI_API_KEY" in st.secrets:
            config["openai_api_key"] = st.secrets["OPENAI_API_KEY"]
        if "YOUTUBE_API_KEY" in st.secrets:
            config["youtube_api_key"] = st.secrets["YOUTUBE_API_KEY"]
    except Exception:
        pass
    return config

api_keys = get_api_keys()
OPENAI_API_KEY = api_keys["openai_api_key"]
YOUTUBE_API_KEY = api_keys["youtube_api_key"]

# --- Helper Functions ---

def get_binary_file_downloader_html(bin_file, file_label='File'):
    """Generate a link to download a binary file."""
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    return f'<a href="data:application/octet-stream;base64,{bin_str}" download="{os.path.basename(file_label)}">Download {file_label}</a>'

def clean_filename(filename):
    """Clean the filename to remove invalid characters."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "_", filename)
    return cleaned.strip('. ')[:100]

def get_video_info(youtube_url):
    """Retrieve basic video info using yt-dlp."""
    try:
        command = ["yt-dlp", "--dump-json", "--no-playlist", "--quiet", youtube_url]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            return {"success": False, "error": result.stderr}
        video_info = json.loads(result.stdout)
        return {
            "success": True,
            "title": video_info.get("title", "Unknown Title"),
            "uploader": video_info.get("uploader", "Unknown Uploader"),
            "duration": video_info.get("duration", 0),
            "thumbnail": video_info.get("thumbnail", "")
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def download_youtube_audio(youtube_url, output_path="./", format="mp3", quality="192"):
    """Download audio from a YouTube video using yt-dlp."""
    try:
        info = get_video_info(youtube_url)
        if not info["success"]:
            return info
        title = info["title"]
        base_filename = clean_filename(title)
        output_file = f"{output_path}/{base_filename}.{format}"
        command = [
            "yt-dlp", "-f", "bestaudio",
            "--extract-audio", "--audio-format", format,
            "--audio-quality", quality,
            "-o", output_file,
            "--no-playlist", "--quiet", "--progress",
            youtube_url
        ]
        progress_bar = st.progress(0)
        status_text = st.empty()
        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode != 0:
            return {"success": False, "error": process.stderr}
        progress_bar.progress(100)
        status_text.empty()
        if not os.path.exists(output_file):
            potential_files = list(Path(output_path).glob(f"{base_filename}.*"))
            if potential_files:
                output_file = str(potential_files[0])
            else:
                return {"success": False, "error": "File not found after download"}
        return {
            "success": True,
            "file_path": output_file,
            "title": title,
            "file_name": os.path.basename(output_file),
            "duration": info["duration"]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def transcribe_with_whisper(audio_file_path):
    """Convert audio to text using OpenAI's Whisper API."""
    import openai
    # Use the API key from secrets or prompt the user if not found.
    api_key = OPENAI_API_KEY if OPENAI_API_KEY else st.text_input("Enter your OpenAI API Key", type="password", key="openai_api_key")
    if not api_key:
        st.error("OpenAI API key is required for transcription.")
        return {"success": False, "error": "No OpenAI API key provided"}
    openai.api_key = api_key
    st.info("Transcribing audio using OpenAI Whisper API. Please wait...")
    try:
        with open(audio_file_path, "rb") as audio_file:
            transcript_response = openai.Audio.transcribe("whisper-1", audio_file)
        transcript_text = transcript_response["text"]
        return {"success": True, "transcript": transcript_text}
    except Exception as e:
        return {"success": False, "error": f"Error transcribing audio with OpenAI: {str(e)}"}

def extract_video_id(url):
    """Extract the video ID from a YouTube URL."""
    # This regex attempts to cover common YouTube URL formats.
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, url)
    if match:
        return match.group(1)
    return None

def get_youtube_comments(video_id, api_key, max_results=100):
    """Fetch top comments for a video using YouTube Data API v3."""
    api_url = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": max_results,
        "order": "relevance",
        "textFormat": "plainText",
        "key": api_key
    }
    response = requests.get(api_url, params=params)
    if response.status_code != 200:
        return {"success": False, "error": f"HTTP error {response.status_code}: {response.text}"}
    data = response.json()
    comments = []
    for item in data.get("items", []):
        snippet = item["snippet"]["topLevelComment"]["snippet"]
        author = snippet.get("authorDisplayName", "Unknown")
        text = snippet.get("textDisplay", "")
        comments.append(f"{author}: {text}")
    return {"success": True, "comments": comments}

# --- Streamlit Application UI ---

st.title("YouTube Audio & Whisper Transcript")
st.markdown(
    "Enter a YouTube URL below, then click **Download Audio** to extract the audio. Once downloaded, click **Generate Transcript** to convert the audio to text using OpenAI's Whisper API. "
    "You can also view the top 100 comments from the video."
)

youtube_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

if st.button("Download Audio"):
    if youtube_url:
        download_result = download_youtube_audio(youtube_url, output_path="downloads")
        if download_result["success"]:
            st.success("Audio downloaded successfully!")
            st.audio(download_result["file_path"])
            st.session_state.audio_file = download_result["file_path"]
        else:
            st.error(f"Error downloading audio: {download_result['error']}")
    else:
        st.warning("Please enter a valid YouTube URL.")

if "audio_file" in st.session_state and st.session_state.audio_file:
    if st.button("Generate Transcript"):
        transcript_result = transcribe_with_whisper(st.session_state.audio_file)
        if transcript_result["success"]:
            st.success("Transcript generated successfully!")
            st.text_area("Transcript", transcript_result["transcript"], height=300)
        else:
            st.error(transcript_result["error"])

# --- Section to display top 100 comments ---
if st.button("Show Top 100 Comments"):
    if youtube_url:
        video_id = extract_video_id(youtube_url)
        if not video_id:
            st.error("Could not extract video ID from the URL.")
        else:
            # Check for YouTube API key
            youtube_api_key = YOUTUBE_API_KEY if YOUTUBE_API_KEY else st.text_input("Enter your YouTube API Key", type="password", key="youtube_api_key")
            if not youtube_api_key:
                st.error("YouTube API key is required to fetch comments.")
            else:
                st.info("Fetching top comments. Please wait...")
                comments_result = get_youtube_comments(video_id, youtube_api_key)
                if comments_result["success"]:
                    comments = comments_result["comments"]
                    if comments:
                        st.success(f"Fetched {len(comments)} comments.")
                        # Display comments in an expander for better readability
                        with st.expander("Top Comments"):
                            for comment in comments:
                                st.write(comment)
                    else:
                        st.info("No comments found for this video.")
                else:
                    st.error(f"Error fetching comments: {comments_result['error']}")
    else:
        st.warning("Please enter a valid YouTube URL.")
