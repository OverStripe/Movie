from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
import os
import threading
from datetime import datetime

# Global variables
clip_duration = 60  # Default duration in seconds
processing_status = {}  # Track processing status for each user


# Function to process and split the video
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


# Command handlers
async def start(update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Set Clip Duration", callback_data="set_duration")],
        [InlineKeyboardButton("Check Status", callback_data="check_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome! Use the buttons below or send me a video to split it into parts with a watermark. "
        "Use /setduration to specify clip duration (default is 60 seconds).",
        reply_markup=reply_markup
    )


async def status(update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    if user_id in processing_status:
        await update.message.reply_text(f"Current Status: {processing_status[user_id]}")
    else:
        await update.message.reply_text("No ongoing video processing task found.")


# Callback query handler for inline buttons
async def button_handler(update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "set_duration":
        await query.message.reply_text(
            "Send the duration in seconds as a message (e.g., `30` for 30 seconds)."
        )
    elif query.data == "check_status":
        user_id = update.effective_user.id
        if user_id in processing_status:
            await query.message.reply_text(f"Current Status: {processing_status[user_id]}")
        else:
            await query.message.reply_text("No ongoing video processing task found.")


# Message handler to set duration
async def set_duration_message(update, context: CallbackContext) -> None:
    global clip_duration
    try:
        duration = int(update.message.text)
        if duration <= 0:
            raise ValueError("Duration must be positive.")
        clip_duration = duration
        await update.message.reply_text(
            f"✅ Clip duration set to {clip_duration} seconds.",
            parse_mode=ParseMode.MARKDOWN
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid duration. Please send a positive number.")


# Video file handler
async def video_handler(update, context: CallbackContext) -> None:
    global clip_duration, processing_status
    user_id = update.effective_user.id

    file = update.message.video or update.message.document
    if file:
        processing_status[user_id] = "Processing"
        await update.message.reply_text(
            f"⏳ Processing your video with a clip duration of {clip_duration} seconds. Please wait...",
            parse_mode=ParseMode.MARKDOWN
        )
        file_path = f"{file.file_id}.mp4"
        output_dir = f"output_{file.file_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        try:
            # Download the video
            await update.message.reply_text("📥 Downloading your video...")
            video = await context.bot.get_file(file.file_id)
            await video.download_to_drive(file_path)

            # Process the video
            await update.message.reply_text("🎥 Processing the video...")
            clips = process_video(file_path, output_dir, clip_duration=clip_duration)

            if clips:
                processing_status[user_id] = "Uploading"
                await update.message.reply_text("📤 Uploading the clips as parts...")
                for i, clip in enumerate(clips, start=1):
                    part_name = f"Part {i}"
                    await context.bot.send_video(
                        chat_id=update.effective_chat.id,
                        video=open(clip, "rb"),
                        caption=f"📹 {part_name}"
                    )
                    os.remove(clip)  # Remove the clip after sending

                processing_status[user_id] = "Completed"
                await update.message.reply_text("✅ All clips uploaded successfully!")
                # Schedule deletion of the output directory
                schedule_deletion(output_dir)
            else:
                processing_status[user_id] = "Failed"
                await update.message.reply_text("❌ Sorry, something went wrong while processing the video.")

            # Remove the original file
            os.remove(file_path)
        except Exception as e:
            processing_status[user_id] = f"Failed: {str(e)}"
            await update.message.reply_text(f"❌ Error: {str(e)}")
    else:
        await update.message.reply_text("❌ Please send me a valid video file.")


# Main function
def main():
    TOKEN = "7294757894:AAFqB4As_i-HzThfalAWfgZ46jkPowF2OB0"
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_duration_message))
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, video_handler))

    application.run_polling()


if __name__ == "__main__":
    main()
    
