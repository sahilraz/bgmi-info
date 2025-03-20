# MongoDB Configuration
MONGODB_ENABLED = True
MONGODB_URI = "mongodb+srv://exp_here:Vaibhav0503M@freecluster.185fa.mongodb.net/?retryWrites=true&w=majority&appName=FreeCluster"
MONGODB_DB = "bgmi_cache"
MONGODB_COLLECTION = "usernames"

# JSON Cache Configuration
JSON_CACHE_ENABLED = True
JSON_CACHE_FILE = "username_cache.json"

# Bot Configuration
OWNER_ID = 7217444967  # Replace with your actual Telegram user ID
TOKEN = "8021336659:AAHuv-SkC9RnNwtwUYMf9UNGzrIsVYjOeic"  # Telegram Bot Token

# Bot UI Configuration
START_IMAGE_URL = "https://graph.org/file/53396de42b15a6f248d99-26191efe9c383fa3a0.jpg"  # URL for the start command image
BOT_THEME = {
    "title_font": "ᴜɴɪᴘɪɴ ᴄʜᴇᴄᴋᴇʀ ʙᴏᴛ",
    "symbols": {
        "success": "✅",
        "error": "❌",
        "warning": "⚠",
        "info": "ℹ️",
        "star": "⭐",
        "flower": "⚘"
    }
}

# Dynamic Configuration
DYNAMIC_CONFIG_RELOAD = True  # Enable/disable dynamic configuration reloading
