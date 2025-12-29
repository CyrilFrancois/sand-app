import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
APP_ENV = os.getenv("APP_ENV", "production")
MAX_VARIANTS = int(os.getenv("MAX_VARIANTS", "4"))
