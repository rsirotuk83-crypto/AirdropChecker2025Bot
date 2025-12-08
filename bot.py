import logging
from aiogram import Bot, Dispatcher, Router
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest # <--- This is the key import
# Configure logging
# The rest of your existing setup is assumed to be here
# ... (including imports, bot/dispatcher initialization, etc.) ...
router = Router()
# --- Placeholder for Admin Panel Markup and Text ---
def get_admin_markup():
    """Generates the inline keyboard for the admin panel."""
    # This is a placeholder, replace with your actual markup logic
    buttons = [
        [InlineKeyboardButton(text="Отримати комбо (Fix)", callback_data="force_fetch_combo")],
        [InlineKeyboardButton(text="Налаштування", callback_data="settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
def get_admin_text():
    """Generates the text content for the admin panel."""
    # This is a placeholder, replace with your actual text logic
    return "Ласкаво просимо до панелі адміністратора. Тут ви можете керувати ботом."
# ---------------------------------------------------
# Function that fails on line 191
@router.callback_query(lambda c: c.data == 'admin_panel' or c.data == 'settings') # Example trigger
async def admin_panel(c: CallbackQuery):
    # This function is around line 191 in your logs
    text = get_admin_text() # Assume this function gets the current text
    markup = get_admin_markup() # Assume this function gets the current markup
    try:
        # We try to edit the message
        await c.message.edit_text(
            text=text,
            reply_markup=markup
        )
    except TelegramBadRequest as e:
        # Check if the error is specifically about the message not being modified
        if "message is not modified" in str(e):
            logging.warning(f"Ignored TelegramBadRequest: {e}. Message content was identical.")
            # If the content is identical, we just ignore the error.
            # This is the fix for the "dormant button" issue.
            await c.answer("Повідомлення вже оновлено.") # Optional: send a brief notification to the user
        else:
            # Re-raise other types of bad requests
            raise
   
    await c.answer() # Always answer the callback query to remove the loading clock
# Function that calls admin_panel on line 222
@router.callback_query(lambda c: c.data == 'force_fetch_combo')
async def force_fetch_combo(c: CallbackQuery):
    # This function is around line 222 in your logs
   
    # 1. Perform the actual action (e.g., fetching new data)
    logging.info("Executing force_fetch_combo logic...")
    # await fetch_new_combo_data() # Placeholder for your logic
   
    # 2. After logic is done, update the admin panel (which might not change)
    await admin_panel(c) # Calls the corrected function
# ...
# The rest of your bot logic (start, message handlers, etc.)
# ...
# And your main polling function
# ...
# The actual fix is in the admin_panel function where the try...except TelegramBadRequest block is used.
