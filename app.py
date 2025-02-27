import streamlit as st
import os
import subprocess

def download_audio(youtube_url, format="mp3"):
    """Downloads the audio from a YouTube video and returns the file path."""
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"audio.{format}")

    command = [
        "yt-dlp",
        "-x",  # Extract audio
        "--audio-format", format,  # Specify format
        "-o", output_path,  # Output path
        youtube_url
    ]

    try:
        subprocess.run(command, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        st.error(f"Error: {e}")
        return None

# Streamlit UI
st.title("YouTube Audio Downloader")

youtube_url = st.text_input("Enter YouTube Video URL")

format_option = st.selectbox("Select Audio Format", ["mp3", "wav", "m4a"])

if st.button("Download Audio"):
    if youtube_url:
        with st.spinner("Downloading audio..."):
            file_path = download_audio(youtube_url, format_option)
            if file_path:
                with open(file_path, "rb") as f:
                    st.download_button(
                        label="Download Audio",
                        data=f,
                        file_name=f"youtube_audio.{format_option}",
                        mime=f"audio/{format_option}",
                    )
    else:
        st.error("Please enter a valid YouTube URL")

