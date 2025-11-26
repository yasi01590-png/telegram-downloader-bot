import os

class Config:
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    API_ID = int(os.environ.get("API_ID", "0"))
    API_HASH = os.environ.get("API_HASH", "")
    ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
    DOWNLOAD_PATH = "./downloads"
    MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
