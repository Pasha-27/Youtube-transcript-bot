import streamlit as st
import os
import subprocess
import base64
import re
from pathlib import Path
import time
import json
import tempfile

# Attempt to import whisper. If not installed, install openai-whisper.
try:
    import whisper
except ModuleNotFoundError:
    st.info("Installing openai-whisper package...")
    subprocess.check_call(["pip", "install", "openai-whisper", "--quiet"])
    import whisper

# Load OpenAI API key from st.secrets if available
@st.cache_resource
def get_api_keys():
    config = {"openai_api_key": None}
    try:
        if "OPENAI_API_KEY" in st.secrets:
            config["openai_api_key"] = st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
    return config

api_keys = get_api_keys()
OPENAI_API_KEY = api_keys["openai_api_key"]

def get_binary_file_downloader_html(bin_file, file_label='File'):
    """Generate a link to download a binary file."""
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{os.path.basename(file_label)}">Download {file_label}</a>'
    return href

def clean_filename(filename):
    """Clean the filename to remove invalid characters"""
    # Replace invalid characters with underscore
    cleaned = re.sub(r'[\\/*?:"<>|]', "_", filename)
    # Remove leading/trailing spaces and dots
    cleaned = cleaned.strip('. ')
    # Limit length
    if len(cleaned) > 100:
        cleaned = cleaned[:100]
    return cleaned

def get_video_info(youtube_url):
    """Get information about the video without downloading it."""
    try:
        # Use yt-dlp to get video information in JSON format
        command = [
            "yt-dlp", 
            "--dump-json", 
            "--no-playlist", 
            "--quiet",
            youtube_url
        ]
        
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            return {"success": False, "error": result.stderr}
        
        # Parse the JSON output
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
    """Download audio from a YouTube video URL using yt-dlp."""
    try:
        # Get video info first
        info = get_video_info(youtube_url)
        if not info["success"]:
            return info
        
        title = info["title"]
        uploader = info["uploader"]
        
        # Create sanitized filename
        base_filename = clean_filename(title)
        output_file = f"{output_path}/{base_filename}.{format}"
        
        # Prepare the yt-dlp command with audio conversion
        command = [
            "yt-dlp",
            "-f", "bestaudio",
            "--extract-audio",
            "--audio-format", format,
            "--audio-quality", quality,
            "-o", output_file,
            "--no-playlist",
            "--quiet",
            "--progress",
            youtube_url
        ]
        
        # Show a progress bar instead of logs
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Run the command without showing output
        process = subprocess.run(command, capture_output=True, text=True)
        
        # Check for errors
        if process.returncode != 0:
            return {"success": False, "error": process.stderr}
        
        # Update progress bar to complete
        progress_bar.progress(100)
        status_text.empty()
        
        # Check if file exists
        if not os.path.exists(output_file):
            # yt-dlp sometimes adds extensions, so try to find the file
            potential_files = list(Path(output_path).glob(f"{base_filename}.*"))
            if potential_files:
                output_file = str(potential_files[0])
            else:
                return {"success": False, "error": "File not found after download"}
        
        return {
            "success": True,
            "file_path": output_file,
            "title": title,
            "author": uploader,
            "file_name": os.path.basename(output_file),
            "duration": info["duration"]
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def transcribe_with_whisper(audio_file_path, model_size="base"):
    """Transcribe audio file using OpenAI's Whisper API."""
    # Use API key from st.secrets or prompt the user if not available
    openai_api_key = OPENAI_API_KEY if OPENAI_API_KEY else st.text_input("Enter your OpenAI API Key", type="password")
    if not openai_api_key:
        st.error("OpenAI API key required for transcription")
        return {"success": False, "error": "No OpenAI API key provided"}
    try:
        import openai
        openai.api_key = openai_api_key
        st.info("Generating transcript with OpenAI Whisper API... This may take a moment.")
        with open(audio_file_path, "rb") as audio_file:
            transcript_response = openai.Audio.transcribe(
                model="whisper-1",
                file=audio_file
            )
        text = transcript_response["text"]
        words = text.split()
        segments = []
        chunk_size = 10  # Number of words per segment
        avg_duration = 2.5  # Average seconds per segment
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i+chunk_size])
            segments.append({
                "start": i / chunk_size * avg_duration,
                "end": (i / chunk_size + 1) * avg_duration,
                "text": chunk
            })
        return {
            "success": True,
            "transcript": text,
            "language": "unknown",  # The API doesn't return language info
            "segments": segments
        }
    except Exception as e:
        return {"success": False, "error": f"Error transcribing audio with OpenAI: {str(e)}"}

# Streamlit UI
st.set_page_config(page_title="YouTube Audio & Whisper Transcript", page_icon="🎵")

st.title("YouTube Audio & Whisper Transcript")
st.markdown("Enter a YouTube URL to download its audio and generate a transcript using OpenAI's Whisper API")

# Check if yt-dlp is installed
try:
    subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
    yt_dlp_installed = True
except FileNotFoundError:
    yt_dlp_installed = False
    st.error("""
    yt-dlp is not installed. You need to install it to use this app:
    ```
    pip install yt-dlp
    ```
    """)

# Input text box for YouTube URL
youtube_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

# Advanced options
with st.expander("Options"):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Audio Options")
        audio_format = st.selectbox("Format", ["mp3", "m4a", "wav", "flac"], index=0)
        audio_quality = st.selectbox("Quality", ["192", "256", "320", "best"], index=2)
    with col2:
        st.subheader("Transcription Options")
        whisper_model = st.selectbox(
            "Whisper Model", 
            ["tiny", "base", "small", "medium", "large"], 
            index=1,
            help="Larger models are more accurate but slower and require more RAM (Note: The OpenAI API currently uses the whisper-1 model)"
        )
        
        show_timestamps = st.checkbox(
            "Show Timestamps", 
            value=False,
            help="Display timestamps for each segment of speech"
        )

# Create directories for downloads if they don't exist
for dir_path in ["downloads", "transcripts"]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# Global state for transcript
if 'transcript' not in st.session_state:
    st.session_state.transcript = None
if 'audio_file' not in st.session_state:
    st.session_state.audio_file = None
if 'download_complete' not in st.session_state:
    st.session_state.download_complete = False

if yt_dlp_installed and st.button("Download Audio"):
    if youtube_url:
        st.session_state.transcript = None
        st.session_state.download_complete = False
        
        with st.spinner("Processing video information..."):
            # Get video info first
            info = get_video_info(youtube_url)
            
            if info["success"]:
                # Create a container for the video information
                video_info_container = st.container()
                with video_info_container:
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.image(info["thumbnail"], width=180)
                    with col2:
                        st.write(f"**Title:** {info['title']}")
                        st.write(f"**Channel:** {info['uploader']}")
                        st.write(f"**Duration:** {time.strftime('%H:%M:%S', time.gmtime(info['duration']))}")
                
                st.write("**Downloading audio...**")
                progress_text = st.empty()
                
                download_container = st.container()
                with download_container:
                    result = download_youtube_audio(
                        youtube_url, 
                        output_path="downloads", 
                        format=audio_format,
                        quality=audio_quality
                    )
                
                if result["success"]:
                    progress_text.empty()
                    st.success(f"Download completed! 🎉")
                    
                    st.session_state.audio_file = result
                    st.session_state.download_complete = True
                    
                    download_container = st.container()
                    with download_container:
                        st.markdown(
                            get_binary_file_downloader_html(result['file_path'], result['file_name']),
                            unsafe_allow_html=True
                        )
                        
                        audio_file = open(result['file_path'], 'rb')
                        audio_bytes = audio_file.read()
                        file_extension = os.path.splitext(result['file_name'])[1][1:]
                        st.audio(audio_bytes, format=f'audio/{file_extension}')
                else:
                    progress_text.empty()
                    st.error(f"Error: {result['error']}")
            else:
                st.error(f"Error retrieving video info: {info['error']}")
    else:
        st.warning("Please enter a YouTube URL")

if st.session_state.download_complete and st.session_state.audio_file:
    if st.button("Generate Transcript with Whisper"):
        audio_info = st.session_state.audio_file
        
        base_filename = os.path.splitext(audio_info['file_name'])[0]
        transcript_filename = f"{base_filename}_{whisper_model}.txt"
        json_filename = f"{base_filename}_{whisper_model}.json"
        
        transcript_path = os.path.join("transcripts", transcript_filename)
        json_path = os.path.join("transcripts", json_filename)
        
        if os.path.exists(transcript_path) and os.path.exists(json_path):
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_text = f.read()
            
            with open(json_path, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
            
            st.session_state.transcript = {
                "success": True, 
                "transcript": transcript_text,
                "language": transcript_data.get("language", "unknown"),
                "segments": transcript_data.get("segments", []),
                "file_path": transcript_path,
                "json_path": json_path
            }
            
            st.success(f"Loaded existing transcript (Whisper {whisper_model})!")
        else:
            with st.spinner(f"Generating transcript with Whisper {whisper_model}... This may take a while."):
                transcript_result = transcribe_with_whisper(
                    audio_info['file_path'], 
                    model_size=whisper_model
                )
                
                if transcript_result["success"]:
                    with open(transcript_path, 'w', encoding='utf-8') as f:
                        f.write(transcript_result["transcript"])
                    
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump({
                            "language": transcript_result["language"],
                            "segments": transcript_result["segments"]
                        }, f, indent=2)
                    
                    transcript_result["file_path"] = transcript_path
                    transcript_result["json_path"] = json_path
                    st.session_state.transcript = transcript_result
                    
                    st.success(f"Transcript generated successfully with Whisper {whisper_model}!")
                    st.info(f"Detected language: {transcript_result['language']}")
                else:
                    st.error(f"Transcription error: {transcript_result['error']}")

if st.session_state.transcript and st.session_state.transcript["success"]:
    st.write("## Transcript")
    
    st.write(f"**Detected Language:** {st.session_state.transcript['language']}")
    
    if show_timestamps and st.session_state.transcript.get("segments"):
        st.write("### Transcript with Timestamps")
        
        for segment in st.session_state.transcript["segments"]:
            start_time = time.strftime('%H:%M:%S', time.gmtime(segment["start"]))
            end_time = time.strftime('%H:%M:%S', time.gmtime(segment["end"]))
            st.write(f"**[{start_time} - {end_time}]** {segment['text']}")
    else:
        st.write(st.session_state.transcript["transcript"])
    
    st.write("### Download Options")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(
            get_binary_file_downloader_html(
                st.session_state.transcript["file_path"], 
                os.path.basename(st.session_state.transcript["file_path"])
            ),
            unsafe_allow_html=True
        )
        st.caption("Download plain text transcript")
    
    with col2:
        st.markdown(
            get_binary_file_downloader_html(
                st.session_state.transcript["json_path"], 
                os.path.basename(st.session_state.transcript["json_path"])
            ),
            unsafe_allow_html=True
        )
        st.caption("Download JSON with timestamps")

st.markdown("---")
st.markdown("### How to use:")
st.markdown("1. Paste a valid YouTube video URL in the input box")
st.markdown("2. Adjust audio format and quality if needed")
st.markdown("3. Select Whisper model size (larger models are more accurate but slower)")
st.markdown("4. Click the 'Download Audio' button")
st.markdown("5. Once download completes, click 'Generate Transcript with Whisper'")
st.markdown("6. View transcript and download files as needed")

st.markdown("---")
st.caption("""
⚠️ Disclaimer: This application is for personal use only. Please respect copyright laws and YouTube's terms of service.
OpenAI's Whisper is an open-source speech recognition model that processes audio via the OpenAI API.
The larger model sizes will require more RAM and processing power when used locally, so the API method is recommended.
""")
