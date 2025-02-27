import streamlit as st
import os
import subprocess
import base64
import re
from pathlib import Path
import time
import json

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
        
        # Prepare the yt-dlp command
        command = [
            "yt-dlp",
            "-f", "bestaudio",
            "--extract-audio",
            "--audio-format", format,
            "--audio-quality", quality,
            "-o", output_file,
            "--no-playlist",
            youtube_url
        ]
        
        # Run the command
        process = subprocess.Popen(
            command, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Real-time output processing
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                st.text(output.strip())
        
        # Check for errors
        stderr = process.stderr.read()
        if process.returncode != 0:
            return {"success": False, "error": stderr}
        
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
            "file_name": os.path.basename(output_file)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# Streamlit UI
st.set_page_config(page_title="YouTube Audio Downloader", page_icon="🎵")

st.title("YouTube Audio Downloader")
st.markdown("Enter a YouTube URL to download its audio")

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
with st.expander("Audio Options"):
    col1, col2 = st.columns(2)
    with col1:
        audio_format = st.selectbox("Format", ["mp3", "m4a", "wav", "flac"], index=0)
    with col2:
        audio_quality = st.selectbox("Quality", ["192", "256", "320", "best"], index=2)

# Create a temporary directory for downloads if it doesn't exist
if not os.path.exists("downloads"):
    os.makedirs("downloads")

if yt_dlp_installed and st.button("Download Audio"):
    if youtube_url:
        with st.spinner("Processing..."):
            # Get video info first
            info = get_video_info(youtube_url)
            
            if info["success"]:
                st.image(info["thumbnail"], width=250)
                st.write(f"**Title:** {info['title']}")
                st.write(f"**Channel:** {info['uploader']}")
                st.write(f"**Duration:** {time.strftime('%H:%M:%S', time.gmtime(info['duration']))}")
            
                # Progress indicator
                progress_text = st.empty()
                progress_text.info("Starting download...")
                
                # Download the audio
                result = download_youtube_audio(
                    youtube_url, 
                    output_path="downloads", 
                    format=audio_format,
                    quality=audio_quality
                )
                
                if result["success"]:
                    progress_text.empty()
                    st.success(f"Download completed! 🎉")
                    
                    # Provide download link
                    st.markdown(
                        get_binary_file_downloader_html(result['file_path'], result['file_name']),
                        unsafe_allow_html=True
                    )
                    
                    # Display audio player
                    audio_file = open(result['file_path'], 'rb')
                    audio_bytes = audio_file.read()
                    st.audio(audio_bytes, format=f'audio/{audio_format}')
                else:
                    progress_text.empty()
                    st.error(f"Error: {result['error']}")
            else:
                st.error(f"Error retrieving video info: {info['error']}")
    else:
        st.warning("Please enter a YouTube URL")

st.markdown("---")
st.markdown("### How to use:")
st.markdown("1. Make sure yt-dlp is installed (`pip install yt-dlp`)")
st.markdown("2. Paste a valid YouTube video URL in the input box")
st.markdown("3. Adjust audio format and quality if needed")
st.markdown("4. Click the 'Download Audio' button")
st.markdown("5. Wait for the download to complete")
st.markdown("6. Use the download link or audio player to access your audio")

# Disclaimer
st.markdown("---")
st.caption("⚠️ Disclaimer: This application is for personal use only. Please respect copyright laws and YouTube's terms of service.")
