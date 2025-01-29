import logging
import random
import string
#import nest_asyncio
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import re
from pymongo import MongoClient

# Apply nest_asyncio to enable running asyncio in Jupyter or similar environments
#nest_asyncio.apply()

# Admin ID and bot token
ADMIN_ID = 6773787379
#TOKEN = "7660007316:AAHis4NuPllVzH-7zsYhXGfgokiBxm_Tml0"

# MongoDB Connection
MONGO_URI = "mongodb+srv://kunalrepowala1:ILPVxpADb0FK7Raa@cluster0.evumw.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.Cluster0  # Database name
media_collection = db.media_links  # Collection for media links

# Set up logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Channel IDs
REQUIRED_CHANNELS = [-1002389931784, -1002351606649]
INVITE_LINKS = {
    -1002389931784: "https://t.me/HotErrorLinks",
    -1002351606649: "https://t.me/HotError"
}

# Function to generate a unique code for each link
def generate_unique_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

# Function to extract links from a text
def extract_link_from_text(text):
    url_pattern = r'(https?://[^\s]+)'
    return re.findall(url_pattern, text)

# Function to check if the user is a member of the required channels
async def is_member_of_channels(user_id, bot):
    member_statuses = await asyncio.gather(
        bot.get_chat_member(REQUIRED_CHANNELS[0], user_id),
        bot.get_chat_member(REQUIRED_CHANNELS[1], user_id)
    )
    return [status.status in ['member', 'administrator', 'creator'] for status in member_statuses]

# Command handler to start the bot and handle the start parameter
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    start_param = update.message.text.split()[1] if len(update.message.text.split()) > 1 else None
    bot = context.bot
    
    # Check if the user is a member of the required channels
    member_statuses = await is_member_of_channels(user_id, bot)
    not_joined_channels = [
        REQUIRED_CHANNELS[i] for i, is_member in enumerate(member_statuses) if not is_member
    ]
    
    if not_joined_channels:
        # Prepare the invite buttons only for channels the user hasn't joined
        invite_buttons = [
            [InlineKeyboardButton(f"Join Channel {i+1}", url=INVITE_LINKS[channel_id])]
            for i, channel_id in enumerate(not_joined_channels)
        ]
        
        # Add a button to retry with the same start link
        if start_param:
            retry_button = InlineKeyboardButton("Joined🧩 (restart)", url=f"https://t.me/{(await context.bot.get_me()).username}?start={start_param}")
            invite_buttons.append([retry_button])

        inline_keyboard = InlineKeyboardMarkup(invite_buttons)
        
        # Send the invite links along with the retry button
        await update.message.reply_text(
            "You need to join the following channel(s) to use the bot:",
            reply_markup=inline_keyboard
        )
        return

    if start_param:
        media_data = media_collection.find_one({"unique_code": start_param})
        
        if media_data:
            media_type = media_data['type']
            media = media_data['media']
            caption = media_data.get('caption', None)
            
            # Extract the link from the caption if available
            web_app_url = None
            if caption:
                extracted_links = extract_link_from_text(caption)
                if extracted_links:
                    web_app_url = extracted_links[0]  # Use the first link found
                    # Remove the URL from the caption
                    caption = re.sub(r'(https?://[^\s]+)', '', caption)

            # Send a warning message
            warning_message = await update.message.reply_text("⚠️ This file will be deleted within 24 Hours. Please take note.")

            # Create the web app button
            if web_app_url:
                web_app_info = WebAppInfo(url=web_app_url)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(text="Play ▶️", web_app=web_app_info)]
                ])
            else:
                keyboard = None

            # Send the media along with the inline keyboard for the mini app
            if media_type == "photo":
                sent_media = await update.message.reply_photo(media, caption=caption, reply_markup=keyboard, protect_content=True)
            elif media_type == "video":
                sent_media = await update.message.reply_video(media, caption=caption, reply_markup=keyboard, protect_content=True)
            elif media_type == "document":
                sent_media = await update.message.reply_document(media, caption=caption, reply_markup=keyboard, protect_content=True)
            elif media_type == "audio":
                sent_media = await update.message.reply_audio(media, caption=caption, reply_markup=keyboard, protect_content=True)
            elif media_type == "sticker":
                sent_media = await update.message.reply_sticker(media, reply_markup=keyboard, protect_content=True)
            elif media_type == "text":
                sent_media = await update.message.reply_text(media, reply_markup=keyboard, protect_content=True)

            # Schedule the deletion in the background without blocking the bot
            asyncio.create_task(delete_media_after_1_minute(sent_media, update, warning_message))
        else:
            await update.message.reply_text("This link does not correspond to any media.")

# New function to delete the media and warning message after 1 minute
async def delete_media_after_1_minute(sent_media, update: Update, warning_message):
    await asyncio.sleep(86400)  # Wait for 1 minute

    # Delete the warning message and the media
    try:
        await warning_message.delete()  # Delete the warning message
        await sent_media.delete()  # Delete the sent media
    except Exception as e:
        logger.error(f"Error deleting message: {e}")

# Message handler to process media from the admin
async def handle_media(update: Update, context: CallbackContext):
    # Check if the update contains a message
    if update.message is None:
        return  # Ignore updates without messages
    
    # Ignore messages from non-admins
    if update.message.from_user.id != ADMIN_ID:
        return
    
    media_type = None
    media = None
    caption = None
    
    if update.message.photo:
        media_type = "photo"
        media = update.message.photo[-1].file_id
        caption = update.message.caption
    elif update.message.video:
        media_type = "video"
        media = update.message.video.file_id
        caption = update.message.caption
    elif update.message.document:
        media_type = "document"
        media = update.message.document.file_id
        caption = update.message.caption
    elif update.message.audio:
        media_type = "audio"
        media = update.message.audio.file_id
        caption = update.message.caption
    elif update.message.voice:
        media_type = "audio"
        media = update.message.voice.file_id
        caption = update.message.caption
    elif update.message.sticker:
        media_type = "sticker"
        media = update.message.sticker.file_id
    elif update.message.text:
        media_type = "text"
        media = update.message.text
    elif update.message.animation:
        media_type = "video"
        media = update.message.animation.file_id
        caption = update.message.caption

    if media_type:
        unique_code = generate_unique_code()
        # Store the media type, media file_id, and caption in MongoDB
        media_collection.insert_one({"unique_code": unique_code, "type": media_type, "media": media, "caption": caption})
        
        # Create the unique start link
        bot_username = (await context.bot.get_me()).username
        start_link = f"https://t.me/{bot_username}?start={unique_code}"
        
        # Send the generated link to the admin
        await update.message.reply_text(f"Here is the unique link: {start_link}")

# Command handler for /list to send all created parameter links with media type
async def list_links(update: Update, context: CallbackContext):
    # Only respond if the message is from the admin
    if update.message.from_user.id != ADMIN_ID:
        return
    
    # Fetch all links from MongoDB
    media_data_list = media_collection.find()
    
    if not media_data_list:
        await update.message.reply_text("No media links have been created yet.")
        return
    
    # Create the list of links with media type
    links = []
    for idx, media_data in enumerate(media_data_list, 1):
        media_type = media_data['type']
        start_link = f"https://t.me/{(await context.bot.get_me()).username}?start={media_data['unique_code']}"
        links.append(f"({idx}) {start_link} {media_type.capitalize()}")

    # Split the list into chunks of 4096 characters or less
    chunk_size = 4096
    message_parts = [links[i:i + chunk_size] for i in range(0, len(links), chunk_size)]
    
    # Send the list in multiple parts
    for part in message_parts:
        await update.message.reply_text("\n".join(part))


# Set up the application and handlers
