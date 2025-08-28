import logging
import os
import subprocess
import asyncio
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
# --- NEW IMPORTS ---
from telegram.request import HTTPXRequest
import telegram.error

from dotenv import load_dotenv, set_key, find_dotenv

# Load .env file if exists
env_path = find_dotenv()
if not env_path:
    env_path = ".env"  # default path if no .env found

load_dotenv(env_path)

# Helper to get or ask for variable
def get_or_ask_env(key: str, prompt: str) -> str:
    value = os.getenv(key)
    if not value:
        value = input(f"{prompt}: ").strip()
        # Save it in the .env file
        set_key(env_path, key, value)
        os.environ[key] = value
    return value

# --- CONFIGURATION ---
TOKEN = get_or_ask_env("BOT_TOKEN", "Enter your Telegram Bot Token")
ADMIN_USER_ID = int(get_or_ask_env("CONTROLLER_ID", "Enter your Telegram User ID (Admin Only)"))

# --- CONFIGURATION ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- NEW: GLOBAL ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs the error and sends a telegram message to notify the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    # This function will be called when an exception is raised.
    # The bot will NOT crash. It will log the error and continue running.


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # (This function remains the same)
    user = update.effective_user
    welcome_message = (
        f"👋 Hello {user.mention_html()}!\n\n"
        f"I am your personal command execution bot.\n"
        f"Your unique Telegram User ID is: <code>{user.id}</code>\n\n"
        "To authorize yourself, copy this ID and paste it into the "
        "<code>ADMIN_USER_ID</code> variable in my source code, then restart me."
    )
    await update.message.reply_html(welcome_message)


async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    command = update.message.text
    logger.info(f"Executing command from admin: {command}")

    processing_message = None
    # --- NEW: Specific try-except block for the initial reply ---
    try:
        processing_message = await update.message.reply_text("⚙️ Running...")
    except telegram.error.TimedOut:
        logger.warning("Network timeout when sending 'Running...' message. Executing command anyway.")
    except Exception as e:
        logger.error(f"Failed to send initial message: {e}")
        # If we can't even send the first message, don't proceed.
        return

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)

        stdout = stdout.decode('utf-8', errors='ignore').strip()
        stderr = stderr.decode('utf-8', errors='ignore').strip()
        return_code = proc.returncode

        output_message = f"<b><u>Command Executed:</u></b>\n<code>{command}</code>\n\n"
        output_message += f"<b><u>Return Code:</u></b> <code>{return_code}</code>\n\n"
        output_message += f"<b><u>STDOUT:</u></b>\n<pre>{stdout or '(No standard output)'}</pre>\n\n"
        output_message += f"<b><u>STDERR:</u></b>\n<pre>{stderr or '(No standard error)'}</pre>"

    except asyncio.TimeoutError:
        output_message = f"❌ <b>Timeout Error!</b>\n\nCommand took too long to execute."
    except Exception as e:
        output_message = f"❌ <b>Execution Error!</b>\n\n<pre>{str(e)}</pre>"

    # Only try to edit the message if we successfully sent it in the first place
    if processing_message:
        # --- NEW: Specific try-except block for the final reply ---
        try:
            if len(output_message) > 4096:
                truncated_message = output_message[:4000] + "\n\n[...] - ✂️ Output truncated."
                await processing_message.edit_text(truncated_message, parse_mode=ParseMode.HTML)
            else:
                await processing_message.edit_text(output_message, parse_mode=ParseMode.HTML)
        except telegram.error.TimedOut:
            logger.warning("Network timeout when editing the final message.")
            # We can't do much here, but we can try sending a new message as a fallback
            await update.message.reply_text("Network error: Could not edit the status message with the result.")
        except telegram.error.BadRequest as e:
            # This can happen if the message content is unchanged, which is fine.
            logger.info(f"Could not edit message (likely no change): {e}")
        except Exception as e:
            logger.error(f"Failed to edit final message: {e}")


async def unauthorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # (This function remains the same)
    user_id = update.effective_user.id
    logger.warning(f"Unauthorized access attempt by user ID: {user_id}")
    await update.message.reply_text("🚫 Sorry, you are not authorized to use this bot.")


def main() -> None:
    """Start the bot."""
    # --- NEW: Configure longer network timeouts ---
    # Default is 5s, we increase it to 10s for connect and 20s for read.
    # This makes the bot more patient on unstable networks like mobile data.
    request = HTTPXRequest(connect_timeout=10.0, read_timeout=20.0)
    
    application = Application.builder().token(TOKEN).request(request).build()

    # --- NEW: Register the global error handler ---
    application.add_error_handler(error_handler)

    # Register other handlers
    admin_filter = filters.User(user_id=ADMIN_USER_ID)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, run_command))
    application.add_handler(MessageHandler(filters.ALL & ~admin_filter, unauthorized))

    logger.info("Bot started and polling...")
    application.run_polling()


if __name__ == '__main__':
    main()
