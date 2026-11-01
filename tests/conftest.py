import os
import sys

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "test")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
