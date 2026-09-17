import os
import sqlite3
import logging
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================
# إعدادات
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

CHANNEL_1 = os.getenv("CHANNEL_1")
CHANNEL_2 = os.getenv("CHANNEL_2")

DB_NAME = "database.db"

# =========================
# Logging
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================
# قاعدة البيانات
# =========================

def init_db():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            caption TEXT
        )
    """)

    conn.commit()
    conn.close()


def add_user(user_id, username, first_name):

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO users
        (user_id, username, first_name)
        VALUES (?, ?, ?)
    """, (
        user_id,
        username,
        first_name
    ))

    conn.commit()
    conn.close()


def get_users():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id
        FROM users
    """)

    users = cursor.fetchall()

    conn.close()

    return [user[0] for user in users]


def add_video(file_id, caption):

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO videos
        (file_id, caption)
        VALUES (?, ?)
    """, (
        file_id,
        caption
    ))

    conn.commit()

    video_id = cursor.lastrowid

    conn.close()

    return video_id


def get_videos():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, file_id, caption
        FROM videos
        ORDER BY id ASC
    """)

    videos = cursor.fetchall()

    conn.close()

    return videos


# =========================
# فحص الاشتراك
# =========================

async def is_subscribed(
    bot,
    user_id,
    channel
):

    try:

        member = await bot.get_chat_member(
            chat_id=channel,
            user_id=user_id
        )

        return member.status in [
            "member",
            "administrator",
            "creator"
        ]

    except Exception as e:

        logger.error(
            f"Subscription check error: {e}"
        )

        return False


async def check_subscription(
    bot,
    user_id
):

    channel1 = await is_subscribed(
        bot,
        user_id,
        CHANNEL_1
    )

    channel2 = await is_subscribed(
        bot,
        user_id,
        CHANNEL_2
    )

    return channel1 and channel2


# =========================
# زر الاشتراك
# =========================

def subscription_keyboard():

    keyboard = [

        [
            InlineKeyboardButton(
                "📢 القناة الأولى",
                url=f"https://t.me/{CHANNEL_1.replace('@', '')}"
            )
        ],

        [
            InlineKeyboardButton(
                "📢 القناة الثانية",
                url=f"https://t.me/{CHANNEL_2.replace('@', '')}"
            )
        ],

        [
            InlineKeyboardButton(
                "✅ تحقق من الاشتراك",
                callback_data="check_subscription"
            )
        ]

    ]

    return InlineKeyboardMarkup(keyboard)


# =========================
# رسالة الاشتراك
# =========================

async def send_subscription_message(
    update,
    context
):

    text = """
🔒 للوصول إلى الفيديوهات يجب عليك الاشتراك في القناتين أولاً.

بعد الاشتراك اضغط:

✅ تحقق من الاشتراك
"""

    if update.callback_query:

        await update.callback_query.message.edit_text(
            text,
            reply_markup=subscription_keyboard()
        )

    else:

        await update.message.reply_text(
            text,
            reply_markup=subscription_keyboard()
        )


# =========================
# START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    add_user(
        user.id,
        user.username,
        user.first_name
    )

    subscribed = await check_subscription(
        context.bot,
        user.id
    )

    if not subscribed:

        await send_subscription_message(
            update,
            context
        )

        return

    await show_videos(
        update,
        context
    )


# =========================
# التحقق من الزر
# =========================

async def check_subscription_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    subscribed = await check_subscription(
        context.bot,
        user_id
    )

    if not subscribed:

        await query.message.edit_text(
            "❌ لم يتم العثور على اشتراك في القناتين.\n\n"
            "اشترك أولاً ثم اضغط تحقق.",
            reply_markup=subscription_keyboard()
        )

        return

    await query.message.edit_text(
        "✅ تم التحقق من الاشتراك."
    )

    await show_videos(
        update,
        context
    )


# =========================
# عرض الفيديوهات
# =========================

async def show_videos(
    update,
    context
):

    user_id = update.effective_user.id

    videos = get_videos()

    if not videos:

        if update.callback_query:

            await update.callback_query.message.reply_text(
                "📂 لا توجد فيديوهات حاليًا."
            )

        else:

            await update.message.reply_text(
                "📂 لا توجد فيديوهات حاليًا."
            )

        return

    keyboard = []

    for video_id, file_id, caption in videos:

        keyboard.append([
            InlineKeyboardButton(
                f"🎬 فيديو {video_id}",
                callback_data=f"video_{video_id}"
            )
        ])

    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:

        await update.callback_query.message.reply_text(
            "🎬 اختر الفيديو:",
            reply_markup=markup
        )

    else:

        await update.message.reply_text(
            "🎬 اختر الفيديو:",
            reply_markup=markup
        )


# =========================
# إرسال الفيديو
# =========================

async def send_selected_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    # فحص الاشتراك مرة أخرى
    subscribed = await check_subscription(
        context.bot,
        user_id
    )

    if not subscribed:

        await query.message.reply_text(
            "❌ يجب أن تكون مشتركًا في القناتين.",
            reply_markup=subscription_keyboard()
        )

        return

    video_id = int(
        query.data.split("_")[1]
    )

    videos = get_videos()

    selected = None

    for video in videos:

        if video[0] == video_id:

            selected = video
            break

    if selected is None:

        await query.message.reply_text(
            "❌ الفيديو غير موجود."
        )

        return

    _, file_id, caption = selected

    try:

        await context.bot.send_video(
            chat_id=user_id,
            video=file_id,
            caption=caption
        )

    except Exception as e:

        logger.error(
            f"Video send error: {e}"
        )

        await query.message.reply_text(
            "❌ حدث خطأ أثناء إرسال الفيديو."
        )


# =========================
# استقبال الفيديو من الأدمن
# =========================

async def receive_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if user_id != ADMIN_ID:

        return

    video = update.message.video

    file_id = video.file_id

    caption = update.message.caption or ""

    video_id = add_video(
        file_id,
        caption
    )

    await update.message.reply_text(
        f"""
✅ تم حفظ الفيديو بنجاح.

🆔 رقم الفيديو:
{video_id}

📦 File ID:
{file_id}
"""
    )


# =========================
# الرسالة الجماعية
# =========================

async def broadcast(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:

        return

    if not context.args:

        await update.message.reply_text(
            "استخدم:\n\n"
            "/broadcast رسالتك هنا"
        )

        return

    text = " ".join(context.args)

    users = get_users()

    success = 0
    failed = 0

    await update.message.reply_text(
        f"📢 بدء الإرسال إلى {len(users)} مستخدم..."
    )

    for user_id in users:

        try:

            await context.bot.send_message(
                chat_id=user_id,
                text=text
            )

            success += 1

        except Exception as e:

            failed += 1

            logger.warning(
                f"Broadcast failed for {user_id}: {e}"
            )

    await update.message.reply_text(
        f"""
✅ انتهى الإرسال.

نجح: {success}
فشل: {failed}
"""
    )


# =========================
# الإحصائيات
# =========================

async def stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:

        return

    users = get_users()
    videos = get_videos()

    await update.message.reply_text(
        f"""
📊 إحصائيات البوت

👥 المستخدمون:
{len(users)}

🎬 الفيديوهات:
{len(videos)}
"""
    )


# =========================
# MAIN
# =========================

def main():

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "broadcast",
            broadcast
        )
    )

    application.add_handler(
        CommandHandler(
            "stats",
            stats
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            check_subscription_callback,
            pattern="^check_subscription$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            send_selected_video,
            pattern="^video_[0-9]+$"
        )
    )

    application.add_handler(
        MessageHandler(
            filters.VIDEO,
            receive_video
        )
    )

    print("Bot is running...")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
