import logging
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder 

# Налаштування логування (бажано, але не обов'язково)
logger = logging.getLogger(__name__)

# Приклад функції для отримання вмісту панелі адміністратора
def get_admin_panel_content(user_id):
    """Генерує текст та клавіатуру для панелі адміністратора."""
    
    # ТУТ МАЄ БУТИ ВАША ЛОГІКА, яка визначає new_text та new_markup
    # Я використовую заглушку для прикладу
    new_text = f"🔒 Панель Адміністратора (UserID: {user_id})\n\n"
    # Додайте реальний статус чи дані комбо сюди
    new_text += "Статус: Готовий. Натисніть 'Оновити', щоб отримати нові дані." 
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Примусово оновити комбо", callback_data="force_fetch_combo")
    builder.button(text="⚙️ Налаштування", callback_data="admin_settings")
    new_markup = builder.as_markup()
    
    return new_text, new_markup

# Виправлена функція admin_panel
async def admin_panel(callback: CallbackQuery):
    """Обробляє відображення панелі адміністратора та оновлення повідомлення."""
    
    # 1. ОБОВ'ЯЗКОВО: Відповісти на запит зворотного виклику
    # Це знімає "крутіння" з кнопки для користувача.
    await callback.answer()
    
    # Отримуємо новий вміст та розмітку
    new_text, new_markup = get_admin_panel_content(callback.from_user.id)
    
    try:
        # Спроба відредагувати повідомлення
        await callback.message.edit_text(
            text=new_text,
            reply_markup=new_markup
        )
    except TelegramBadRequest as e:
        # Перехоплюємо тільки помилку "message is not modified"
        if "message is not modified" in str(e):
            # Ігноруємо помилку, якщо повідомлення не змінилося. 
            # Це нормальна поведінка, коли користувач натискає двічі.
            logger.info("Handled harmless TelegramBadRequest: message is not modified.")
        else:
            # Для будь-яких інших TelegramBadRequest (наприклад, message not found), 
            # перекидаємо помилку далі для обробки.
            logger.error(f"Unexpected TelegramBadRequest in admin_panel: {e}")
            raise e
    except Exception as e:
        # Обробка інших можливих помилок
        logger.error(f"An unexpected error occurred in admin_panel: {e}")


# Приклад того, як force_fetch_combo викликає admin_panel
async def force_fetch_combo(callback: CallbackQuery):
    """Логіка оновлення комбо, а потім виклик admin_panel."""
    
    # 1. ТУТ МАЄ БУТИ ВАША ЛОГІКА, яка виконує оновлення комбо/даних
    logger.info("Starting force combo fetch...")
    # await update_combo_data() 
    
    # 2. Оновлення панелі адміністратора з новими даними
    await admin_panel(callback)
