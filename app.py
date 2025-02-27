import streamlit as st
import os
import pytube
from pytube import YouTube
import base64
from io import BytesIO

def get_binary_file_downloader_html(bin_file, file_label='File'):
    """
    Generate a link to download a binary file.
    """
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{os.path.basename(file_label)}">Download {file_label}</a>'
    return href

def download_youtube_audio(youtube_url, output_path="./"):
    """
    Download audio from a YouTube video URL
    """
    try:
        # Create YouTube object
        yt = YouTube(youtube_url)
        
        # Get the audio stream (highest quality audio)
        audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
        
        # Get the original file extension
        file_extension = audio_stream.subtype
        
        # Create a filename from the video title
        file_name = f"{yt.title}.{file_extension}"
        # Clean the filename to remove any invalid characters
        file_name = "".join([c for c in file_name if c.isalpha() or c.isdigit() or c==' ' or c=='.']).rstrip()
        
        # Download the file
        audio_file = audio_stream.download(output_path=output_path, filename=file_name)
        
        return {
            "success": True,
            "file_path": audio_file,
            "title": yt.title,
            "author": yt.author,
            "file_name": file_name
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Streamlit UI
st.set_page_config(page_title="YouTube Audio Downloader", page_icon="🎵")

st.title("YouTube Audio Downloader")
st.markdown("Enter a YouTube URL to download its audio")

# Input text box for YouTube URL
youtube_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

# Create a temporary directory for downloads if it doesn't exist
if not os.path.exists("temp_downloads"):
    os.makedirs("temp_downloads")

if st.button("Download Audio"):
    if youtube_url:
        with st.spinner("Downloading audio... Please wait."):
            # Show progress information
            st.info("Starting download process...")
            
            # Download the audio
            result = download_youtube_audio(youtube_url, output_path="temp_downloads")
            
            if result["success"]:
                st.success(f"Download completed! 🎉")
                st.markdown(f"**Title:** {result['title']}")
                st.markdown(f"**Channel:** {result['author']}")
                
                # Provide download link
                st.markdown(
                    get_binary_file_downloader_html(result['file_path'], result['file_name']),
                    unsafe_allow_html=True
                )
                
                # Display audio player
                audio_file = open(result['file_path'], 'rb')
                audio_bytes = audio_file.read()
                st.audio(audio_bytes, format=f'audio/{result["file_name"].split(".")[-1]}')
            else:
                st.error(f"Error: {result['error']}")
    else:
        st.warning("Please enter a YouTube URL")

st.markdown("---")
st.markdown("### How to use:")
st.markdown("1. Paste a valid YouTube video URL in the input box above")
st.markdown("2. Click the 'Download Audio' button")
st.markdown("3. Wait for the download to complete")
st.markdown("4. Use the download link or audio player to access your audio")

# Disclaimer
st.markdown("---")
st.caption("⚠️ Disclaimer: This application is for personal use only. Please respect copyright laws and YouTube's terms of service.")
