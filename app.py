import streamlit as st
import os
import subprocess
import base64
import re
from pathlib import Path
import time
import json
import speech_recognition as sr
from pydub import AudioSegment
import tempfile

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
            "--quiet",  # Added quiet flag to suppress logs
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
            "--quiet",  # Added quiet flag to suppress logs
            "--progress",  # Still track progress but with minimal output
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

def transcribe_audio(audio_file_path, duration):
    """Transcribe audio file using Google's speech recognition."""
    try:
        # Initialize recognizer
        r = sr.Recognizer()
        
        # For long audio files, split into chunks to avoid timeout issues
        if duration > 60:  # If longer than 1 minute
            return transcribe_long_audio(audio_file_path, duration)
        
        # Convert audio file to WAV format for processing if it's not already WAV
        file_extension = os.path.splitext(audio_file_path)[1][1:].lower()
        
        if file_extension == 'wav':
            # If already WAV, use directly
            with sr.AudioFile(audio_file_path) as source:
                audio_data = r.record(source)
                
                # Use Google's speech recognition
                transcript = r.recognize_google(audio_data)
                return {"success": True, "transcript": transcript}
        else:
            # Convert to WAV first
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name
            
            # Load audio and export as WAV
            audio = AudioSegment.from_file(audio_file_path, format=file_extension)
            audio.export(temp_wav_path, format="wav")
            
            # Process WAV file
            with sr.AudioFile(temp_wav_path) as source:
                audio_data = r.record(source)
                
                # Use Google's speech recognition
                transcript = r.recognize_google(audio_data)
                
                # Clean up temporary file
                os.unlink(temp_wav_path)
                
                return {"success": True, "transcript": transcript}
    
    except sr.UnknownValueError:
        return {"success": False, "error": "Speech Recognition could not understand the audio"}
    except sr.RequestError as e:
        return {"success": False, "error": f"Could not request results from Speech Recognition service; {e}"}
    except Exception as e:
        return {"success": False, "error": f"Error transcribing audio: {str(e)}"}

def transcribe_long_audio(audio_file_path, duration):
    """Handle longer audio files by splitting into chunks."""
    try:
        # Load the audio file
        file_extension = os.path.splitext(audio_file_path)[1][1:].lower()
        audio = AudioSegment.from_file(audio_file_path, format=file_extension)
        
        # Initialize recognizer
        r = sr.Recognizer()
        
        # Split into 30-second chunks
        chunk_length_ms = 30 * 1000  # 30 seconds
        chunks = [audio[i:i+chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
        
        # Progress indicator
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.info("Transcribing audio (this may take a while)...")
        
        # Process each chunk
        full_transcript = []
        for i, chunk in enumerate(chunks):
            # Update progress
            progress = int((i / len(chunks)) * 100)
            progress_bar.progress(progress)
            status_text.info(f"Transcribing part {i+1} of {len(chunks)}...")
            
            # Export chunk to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name
            
            chunk.export(temp_wav_path, format="wav")
            
            # Transcribe chunk
            with sr.AudioFile(temp_wav_path) as source:
                audio_data = r.record(source)
                
                try:
                    # Use Google's speech recognition
                    chunk_transcript = r.recognize_google(audio_data)
                    full_transcript.append(chunk_transcript)
                except sr.UnknownValueError:
                    # If this chunk couldn't be transcribed, add a placeholder
                    full_transcript.append("[Unclear audio]")
                except sr.RequestError:
                    # If there was a network error, try again after a delay
                    time.sleep(2)
                    try:
                        chunk_transcript = r.recognize_google(audio_data)
                        full_transcript.append(chunk_transcript)
                    except:
                        full_transcript.append("[Recognition error]")
            
            # Clean up temporary file
            os.unlink(temp_wav_path)
            
            # Add a small delay to avoid hitting API rate limits
            time.sleep(0.5)
        
        # Complete progress
        progress_bar.progress(100)
        status_text.empty()
        
        # Join all transcribed chunks
        complete_transcript = " ".join(full_transcript)
        
        return {"success": True, "transcript": complete_transcript}
    
    except Exception as e:
        return {"success": False, "error": f"Error transcribing long audio: {str(e)}"}

# Streamlit UI
st.set_page_config(page_title="YouTube Audio & Transcript Downloader", page_icon="🎵")

st.title("YouTube Audio & Transcript Downloader")
st.markdown("Enter a YouTube URL to download its audio and generate a transcript")

# Check if yt-dlp is installed
try:
    # Run with quiet flag to hide version output
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

# FFmpeg is available, so we don't need to check or warn

# Input text box for YouTube URL
youtube_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

# Advanced options
with st.expander("Audio Options"):
    col1, col2 = st.columns(2)
    with col1:
        audio_format = st.selectbox("Format", ["mp3", "m4a", "wav", "flac"], index=0)
    with col2:
        audio_quality = st.selectbox("Quality", ["192", "256", "320", "best"], index=2)

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
                
                # Progress indicator
                st.write("**Downloading audio...**")
                progress_text = st.empty()
                
                # FFmpeg is available, so no warning needed
                
                # Download the audio
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
                    
                    # Store audio file path in session state
                    st.session_state.audio_file = result
                    st.session_state.download_complete = True
                    
                    # Provide download link
                    download_container = st.container()
                    with download_container:
                        st.markdown(
                            get_binary_file_downloader_html(result['file_path'], result['file_name']),
                            unsafe_allow_html=True
                        )
                        
                        # Display audio player
                        audio_file = open(result['file_path'], 'rb')
                        audio_bytes = audio_file.read()
                        file_extension = os.path.splitext(result['file_name'])[1][1:]  # Get extension without dot
                        st.audio(audio_bytes, format=f'audio/{file_extension}')
                else:
                    progress_text.empty()
                    st.error(f"Error: {result['error']}")
            else:
                st.error(f"Error retrieving video info: {info['error']}")
    else:
        st.warning("Please enter a YouTube URL")

# Only show the transcribe button if download is complete
if st.session_state.download_complete and st.session_state.audio_file:
    if st.button("Generate Transcript"):
        audio_info = st.session_state.audio_file
        
        # Check if transcript file already exists to avoid regenerating
        transcript_filename = os.path.splitext(audio_info['file_name'])[0] + ".txt"
        transcript_path = os.path.join("transcripts", transcript_filename)
        
        if os.path.exists(transcript_path):
            # Load existing transcript
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_text = f.read()
            
            st.session_state.transcript = {
                "success": True, 
                "transcript": transcript_text,
                "file_path": transcript_path
            }
            st.success("Loaded existing transcript!")
        else:
            # Generate new transcript
            with st.spinner("Generating transcript... This may take a while depending on audio length"):
                transcript_result = transcribe_audio(audio_info['file_path'], audio_info['duration'])
                
                if transcript_result["success"]:
                    # Save transcript to file
                    with open(transcript_path, 'w', encoding='utf-8') as f:
                        f.write(transcript_result["transcript"])
                    
                    transcript_result["file_path"] = transcript_path
                    st.session_state.transcript = transcript_result
                    st.success("Transcript generated successfully!")
                else:
                    st.error(f"Transcription error: {transcript_result['error']}")

# Display transcript if available
if st.session_state.transcript and st.session_state.transcript["success"]:
    st.write("## Transcript")
    st.write(st.session_state.transcript["transcript"])
    
    # Provide download link for transcript
    st.markdown(
        get_binary_file_downloader_html(
            st.session_state.transcript["file_path"], 
            os.path.basename(st.session_state.transcript["file_path"])
        ),
        unsafe_allow_html=True
    )

st.markdown("---")
st.markdown("### How to use:")
st.markdown("1. Paste a valid YouTube video URL in the input box")
st.markdown("2. Adjust audio format and quality if needed")
st.markdown("3. Click the 'Download Audio' button")
st.markdown("4. Once download completes, click 'Generate Transcript' to create a transcript")
st.markdown("5. Download the audio or transcript files as needed")

# Disclaimer
st.markdown("---")
st.caption("""
⚠️ Disclaimer: This application is for personal use only. Please respect copyright laws and YouTube's terms of service.
The transcript feature uses Google's speech recognition API and may not be perfectly accurate, especially for longer videos or those with background noise.
""")
