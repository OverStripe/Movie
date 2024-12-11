from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode

# Start command handler
async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Set Clip Duration", callback_data="set_duration")],
        [InlineKeyboardButton("Check Status", callback_data="check_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome! Here are your options:",
        reply_markup=reply_markup
    )

# Callback query handler for inline buttons
async def button_handler(update: Update, context: CallbackContext) -> None:
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

# Duration message handler
async def set_duration_message(update: Update, context: CallbackContext) -> None:
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
async def video_handler(update: Update, context: CallbackContext) -> None:
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
    application.add_handler(CommandHandler("setduration", set_duration_message))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_duration_message))
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, video_handler))

    application.run_polling()
