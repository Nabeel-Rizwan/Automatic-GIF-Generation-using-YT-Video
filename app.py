from flask import Flask, render_template, request, send_file
import os
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
import moviepy.editor as mp
from PIL import Image, ImageDraw, ImageFont
import imageio
import numpy as np
import shutil
import zipfile


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/gifs'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit upload size to 16MB
app.config['ZIP_FILE'] = 'gifs.zip'


# Function to delete all GIFs in the static/gifs directory
def clear_gif_folder():
    folder = app.config['UPLOAD_FOLDER']
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"An error occurred while deleting file {file_path}: {e}")

# Function to delete gifs.zip if it exists
def clear_zip_file():
    zip_file = app.config['ZIP_FILE']
    if os.path.exists(zip_file):
        os.remove(zip_file)

# Function to download YouTube video
def download_youtube_video(youtube_url, download_path):
    try:
        yt = YouTube(youtube_url)
        yt_stream = yt.streams.filter(file_extension='mp4').first()
        yt_stream.download(filename=download_path)
        return download_path
    except Exception as e:
        print(f"An error occurred while downloading the video: {e}")
        return None

# Function to extract YouTube transcript
def extract_transcript(youtube_url):
    try:
        video_id = youtube_url.split("v=")[-1]
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:
        print(f"An error occurred while extracting the transcript: {e}")
        return None

# Function to create GIF from video frames with text overlay
def create_gif_with_text(frames, text, output_path):
    try:
        font_path = "font.ttf"  # Update this path to your font file
        font = ImageFont.truetype(font_path, 30)
        gif_frames = []
        for frame in frames:
            # Convert frame to PIL Image
            img_pil = Image.fromarray(frame.astype('uint8'), 'RGB')
            draw = ImageDraw.Draw(img_pil)

            # Add black background rectangle for text
            text_width, text_height = draw.textsize(text, font=font)
            text_position = ((img_pil.width - text_width) // 2, img_pil.height - text_height - 10)
            draw.rectangle([text_position, (text_position[0] + text_width, text_position[1] + text_height)], fill="black")
            draw.text(text_position, text, font=font, fill="white")
            gif_frames.append(np.array(img_pil))  # Append numpy array representation

        # Save the frames as a GIF using imageio
        imageio.mimsave(output_path, gif_frames, loop=0)
        print(f"Created GIF: {output_path}")

    except Exception as e:
        print(f"An error occurred while creating GIF: {e}")

# Gif with no transcript
def create_gif_with_no_transcript(video_path, gif_path):
    try:
        # Load the video using MoviePy
        video = mp.VideoFileClip(video_path)
        
        # Extract frames from the video
        frames = [frame for frame in video.iter_frames()]
                
        # Save frames as a GIF using imageio
        imageio.mimsave(gif_path, frames, loop=0)
        
        print(f"Created GIF: {gif_path}")
        
    except Exception as e:
        print(f"An error occurred while creating GIF: {e}")

# Main route to upload YouTube link and display GIFs
@app.route('/', methods=['GET', 'POST'])
def index():
    # Clear the GIF folder and zip file on page reload
    clear_gif_folder()
    clear_zip_file()


    gif_paths = []
    if request.method == 'POST':
        youtube_link = request.form['youtube_link']
        if youtube_link:
            try:
                # Download YouTube video
                download_path = 'downloaded_video.mp4'
                video_path = download_youtube_video(youtube_link, download_path)

                if video_path:
                    # Extract YouTube transcript
                    transcript = extract_transcript(youtube_link)

                    if transcript:
                        video = mp.VideoFileClip(video_path)
                        output_dir = app.config['UPLOAD_FOLDER']
                        if not os.path.exists(output_dir):
                            os.makedirs(output_dir)

                        gif_paths = []
                        for idx, entry in enumerate(transcript):
                            start_time = entry['start']
                            end_time = start_time + entry['duration']  # Ensure the clip covers the entire duration of the transcript entry
                            text = entry['text']

                            subclip = video.subclip(start_time, end_time)
                            frames = list(subclip.iter_frames())

                            # Create text for GIF
                            gif_text = f"{text}"  # Whole sentence of the transcript
                            gif_path = os.path.join(output_dir, f"output_gif_{idx}.gif")
                            create_gif_with_text(frames, gif_text, gif_path)
                            gif_paths.append(f"gifs/output_gif_{idx}.gif")

                        # Clean up the downloaded video file
                        os.remove(video_path)

                    else:
                        print("No transcript available in the video.")
                        # Generate GIF without transcript
                        output_dir = app.config['UPLOAD_FOLDER']
                        if not os.path.exists(output_dir):
                            os.makedirs(output_dir)
                        gif_path = os.path.join(output_dir, "output_gif.gif")
                        create_gif_with_no_transcript(video_path, gif_path)
                        os.remove(video_path)
                        gif_paths.append("gifs/output_gif.gif")

                else:
                    print("Failed to download the video.")

            except Exception as e:
                print(f"An error occurred: {e}")
                return render_template('index.html', gif_paths=gif_paths, error=True)

        else:
            print("No YouTube link provided.")

    return render_template('index.html', gif_paths=gif_paths)


# Route to download the entire 'gifs' folder as a zip file
@app.route('/download_gifs', methods=['GET'])
def download_gifs():
    try:
        gifs_folder = 'static/gifs'
        zipf = zipfile.ZipFile('gifs.zip', 'w', zipfile.ZIP_DEFLATED)
        for root, dirs, files in os.walk(gifs_folder):
            for file in files:
                zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), os.path.join(gifs_folder, '..')))
        zipf.close()
        return send_file('gifs.zip', as_attachment=True)
    except Exception as e:
        print(f"An error occurred while downloading GIFs folder: {e}")
        return render_template('index.html', error=True)


if __name__ == "__main__":
    app.run(debug=True)
