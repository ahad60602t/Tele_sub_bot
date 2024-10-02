
import sqlite3
import os
import time
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

load_dotenv()

# Get credentials from .env file
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize the bot
app = Client("logobot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Database setup
def db_setup():
    with sqlite3.connect("subscriptions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                subscribed INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                password TEXT NOT NULL
            )
        """)
        cursor.execute("SELECT COUNT(*) FROM admin")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO admin (password) VALUES (?)", ("",))  # Change to your secure password
        conn.commit()

db_setup()

# Admin Functions
def check_admin_password(password):
    with sqlite3.connect("subscriptions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin WHERE password = ?", (password,))
        admin = cursor.fetchone()
        return admin is not None

def approve_user(user_id):
    with sqlite3.connect("subscriptions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET approved = 1 WHERE user_id = ?", (user_id,))
        conn.commit()

def is_approved(user_id):
    with sqlite3.connect("subscriptions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT approved FROM users WHERE user_id = ?", (user_id,))
        approved = cursor.fetchone()
        return approved and approved[0] == 1

def add_user(user_id, email, password):
    for _ in range(5):  # Retry up to 5 times
        try:
            with sqlite3.connect("subscriptions.db") as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (user_id, email, password, approved) VALUES (?, ?, ?, ?)", 
                               (user_id, email, password, 0))
                conn.commit()
            break  # Exit loop if successful
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                time.sleep(1)  # Wait before retrying
            else:
                raise  # Raise any other error

def get_pending_users():
    with sqlite3.connect("subscriptions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, email FROM users WHERE approved = 0")
        users = cursor.fetchall()
        return users

# Admin Tools
async def post_maker(bot, message):
    await message.reply_text("Please send the post content:")
    @app.on_message(filters.private & filters.text)
    async def process_post(bot, message):
        if message.text.startswith("/"): return  # Skip commands
        await bot.send_message(message.chat.id, f"📝 Post Created: {message.text}")

async def poll_maker(bot, message):
    await message.reply_text("Please send the poll question and options in this format:\n\n`Question | Option1, Option2, Option3`")
    
    @app.on_message(filters.private & filters.text)
    async def process_poll(bot, message):
        if message.text.startswith("/"): return  # Skip commands
        try:
            question, options = message.text.split('|')
            options = options.split(',')
            await bot.send_poll(chat_id=message.chat.id, question=question.strip(), options=[opt.strip() for opt in options])
        except ValueError:
            await message.reply_text("❌ Invalid format. Use `Question | Option1, Option2, Option3`.")

# Command Handlers

@app.on_message(filters.command("start"))
async def start(bot, message):
    welcome_message = (
        "👋 Welcome to the bot!\n\n"
        "Please choose an option:\n"
        "1. /admin_login - Admin Login\n"
        "2. /user_login - User Login\n"
        "3. /register - User Registration"
    )
    await message.reply_text(welcome_message)

@app.on_message(filters.command("admin_login"))
async def admin_login(bot, message):
    await message.reply_text("Please enter your admin password:")

@app.on_message(filters.private & filters.text)
async def validate_admin(bot, message):
    if message.text.startswith("/"): return  # Skip commands

    password = message.text
    if check_admin_password(password):
        await message.reply_text("✅ Admin access granted. Use /admin_panel to manage users and access tools.")
    else:
        await message.reply_text("❌ Invalid password. Please try again.")

@app.on_message(filters.command("register"))
async def register_user(bot, message):
    await message.reply_text("Please send your email and password in this format:\n\n`email@example.com password123`")

@app.on_message(filters.private & filters.text)
async def process_registration(bot, message):
    if message.text.startswith("/"): return  # Skip commands

    try:
        email, password = message.text.split()
        add_user(message.from_user.id, email, password)
        await message.reply_text("✅ Registration successful. Please proceed to pay the subscription fee to the following Bkash number: 01722304366\n\n"
                                  "After payment, send /request_permission to ask for admin approval.")
    except ValueError:
        await message.reply_text("❌ Invalid format. Please send your email and password in this format:\n\n`email@example.com password123`")

@app.on_message(filters.command("request_permission"))
async def request_permission(bot, message):
    if not is_approved(message.from_user.id):
        await message.reply_text("⏳ Your request for admin approval has been sent. Please wait for approval.")
        admin_chat_id = 6441392640  # Replace with actual admin chat ID
        await bot.send_message(admin_chat_id, f"User {message.from_user.id} has requested permission to access the channel.")
    else:
        await message.reply_text("✅ You are already approved.")

@app.on_message(filters.command("user_login"))
async def user_login(bot, message):
    await message.reply_text("Please enter your email and password in this format:\n\n`email@example.com password123`")

@app.on_message(filters.private & filters.text)
async def process_login(bot, message):
    if message.text.startswith("/"): return  # Skip commands

    try:
        email, password = message.text.split()
        with sqlite3.connect("subscriptions.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT approved FROM users WHERE email = ? AND password = ?", (email, password))
            user = cursor.fetchone()

        if user:
            if user[0] == 1:
                await message.reply_text("✅ Login successful. You are approved to access the channels.")
            else:
                await message.reply_text("⏳ Your account is pending admin approval.")
        else:
            await message.reply_text("❌ Invalid login credentials.")
    except ValueError:
        await message.reply_text("❌ Invalid format. Please send your email and password in this format:\n\n`email@example.com password123`")

@app.on_message(filters.command("admin_panel") & filters.private)
async def admin_panel(bot, message):
    await message.reply_text(
        "⚙️ Admin Panel:\n\nChoose an option:",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Approve Users", callback_data="approve_users")],
                [InlineKeyboardButton("Poll Maker", callback_data="poll_maker")],
                [InlineKeyboardButton("Post Maker", callback_data="post_maker")],
                [InlineKeyboardButton("Manage Channels", callback_data="manage_channels")],
                [InlineKeyboardButton("Logout", callback_data="admin_logout")]
            ]
        )
    )

@app.on_callback_query(filters.regex("admin_logout"))
async def admin_logout(bot, query):
    await query.message.edit_text("🔒 Admin logged out.")

@app.on_callback_query(filters.regex("approve_users"))
async def approve_users(bot, query):
    pending_users = get_pending_users()
    if not pending_users:
        await query.message.edit_text("No users are pending approval.")
        return

    buttons = []
    for user in pending_users:
        buttons.append([InlineKeyboardButton(f"Approve {user[1]}", callback_data=f"approve_{user[0]}")])

    await query.message.edit_text(
        "Pending users for approval:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r"approve_"))
async def approve_user(bot, query):
    user_id = query.data.split("_")[1]
    approve_user(user_id)
    await query.answer(f"User {user_id} approved.")
    await query.message.delete()

@app.on_callback_query(filters.regex("poll_maker"))
async def poll_maker_callback(bot, query):
    await poll_maker(bot, query.message)

@app.on_callback_query(filters.regex("post_maker"))
async def post_maker_callback(bot, query):
    await post_maker(bot, query.message)

# Channel Management

