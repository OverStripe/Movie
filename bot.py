from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
import os
import threading
from datetime import datetime

# Define a function to process and split the video
def process_video(file_path, output_dir, clip_duration=60, watermark="@Philo.Cinemas", target_aspect_ratio=(9, 16)):
    try:
        clip = VideoFileClip(file_path)
        duration = clip.duration  # Total duration of the video
        os.makedirs(output_dir, exist_ok=True)  # Create output directory

        clips = []
        for start in range(0, int(duration), clip_duration):
            end = min(start + clip_duration, duration)
            subclip = clip.subclip(start, end)

            # Resize video to 9:16 format
            width, height = subclip.size
            target_width = width
            target_height = int((target_width / target_aspect_ratio[0]) * target_aspect_ratio[1])
            resized_clip = subclip.resize(height=target_height)

            # Add watermark
            watermark_clip = TextClip(watermark, fontsize=50, color='white', bg_color='black', font='Arial')
            watermark_clip = watermark_clip.set_position(("center", "bottom")).set_duration(resized_clip.duration)

            # Combine watermark with video
            final_clip = CompositeVideoClip([resized_clip, watermark_clip])

            # Output file path
            output_file = os.path.join(output_dir, f"clip_{start}_{int(end)}.mp4")
            final_clip.write_videofile(output_file, codec="libx264", audio_codec="aac")
            clips.append(output_file)
        clip.close()
        return clips
    except Exception as e:
        print(f"Error processing video: {e}")
        return []

# Function to delete files after 24 hours
def schedule_deletion(directory):
    def delete_files():
        print(f"Deleting files in {directory}...")
        for file in os.listdir(directory):
            file_path = os.path.join(directory, file)
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")
        os.rmdir(directory)  # Remove the directory after deleting files
        print(f"Deleted directory: {directory}")
    
    # Schedule the deletion after 1 day (86400 seconds)
    timer = threading.Timer(86400, delete_files)
    timer.start()

# Start command handler
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Welcome! Send me a video file, and I will split it into 1-minute vertical parts with watermark (e.g., Part 1, Part 2, etc.). Files will be deleted after 1 day.")

# Video file handler
async def video_handler(update: Update, context: CallbackContext) -> None:
    file = update.message.video or update.message.document
    if file:
        await update.message.reply_text("Processing your video. Please wait...")
        file_path = f"{file.file_id}.mp4"
        output_dir = f"output_{file.file_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Download the video
        video = await context.bot.get_file(file.file_id)
        await video.download_to_drive(file_path)
        
        # Process the video
        clips = process_video(file_path, output_dir)
        
        if clips:
            await update.message.reply_text("Uploading the clips as parts...")
            for i, clip in enumerate(clips, start=1):
                part_name = f"Part {i}"
                await context.bot.send_video(chat_id=update.effective_chat.id, video=open(clip, "rb"), caption=part_name)
                os.remove(clip)  # Remove the clip after sending
            
            # Schedule deletion of the output directory
            schedule_deletion(output_dir)
        else:
            await update.message.reply_text("Sorry, something went wrong while processing the video.")
        
        # Remove the original file
        os.remove(file_path)
    else:
        await update.message.reply_text("Please send me a valid video file.")

# Main function
def main():
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token from BotFather
    TOKEN = "7294757894:AAFtGulgOEpcXAQIGCgP_StFE02mhovnG9c"
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, video_handler))

    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
    
