from pydantic_settings import BaseSettings, NoDecode
from pydantic import field_validator
from typing import List, Union
from typing_extensions import Annotated
import json

class Settings(BaseSettings):
    PROJECT_NAME: str = "FloodSafe API"
    API_V1_STR: str = "/api"

    # Database - MUST be overridden in production via DATABASE_URL env var
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/floodsafe"

    # CORS Configuration
    # For production, set env var: BACKEND_CORS_ORIGINS=https://your-frontend.vercel.app (single URL)
    # OR: BACKEND_CORS_ORIGINS=https://url1.com,https://url2.com (comma-separated)
    # OR: BACKEND_CORS_ORIGINS=["https://your-frontend.vercel.app"] (JSON array)
    # NoDecode prevents pydantic-settings from JSON-parsing before our validator runs
    BACKEND_CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:5175",
        "http://localhost:8000",
        "http://localhost",  # Capacitor Android WebView origin (no port)
        "https://frontend-lime-psi-83.vercel.app",
        "https://floodsafe.live",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from various formats: JSON array, comma-separated, or single URL."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Try JSON array first: ["url1", "url2"]
            if v.startswith("["):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass
            # Try comma-separated: url1,url2
            if "," in v:
                return [url.strip() for url in v.split(",") if url.strip()]
            # Single URL
            if v.strip():
                return [v.strip()]
        return []

    # Flag to detect if we're in production (check if DATABASE_URL changed from default)
    @property
    def is_production(self) -> bool:
        return "localhost" not in self.DATABASE_URL

    # JWT Authentication
    JWT_SECRET_KEY: str = "floodsafe-jwt-secret-change-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Firebase (for phone auth)
    FIREBASE_PROJECT_ID: str = ""

    # Mapbox (for routing)
    MAPBOX_ACCESS_TOKEN: str = ""

    # Embedded ML Configuration
    # ML models are now embedded in backend (no separate ML service)
    ML_ENABLED: bool = True                # Enable embedded ML models (XGBoost + TFLite)
    ML_MODELS_DIR: str = "./models"        # Path to model files
    ML_DATA_DIR: str = "./data"            # Path to data files (hotspots JSON)
    ML_SERVICE_URL: str = ""               # Legacy: external ML service URL (unused, embedded TFLite now)

    # ML Routing Integration (gradual rollout)
    ML_ROUTING_ENABLED: bool = False       # Enable ML predictions in route comparison
    ML_ROUTING_WEIGHT: float = 0.3         # Weight of ML vs reports/sensors [0-1]
    ML_MIN_CONFIDENCE: float = 0.7         # Only use predictions above this confidence
    ML_CACHE_TTL_SECONDS: int = 300        # Cache ML predictions for 5 min

    # External Alerts Configuration
    RSS_FEEDS_ENABLED: bool = True         # Enable RSS news fetcher
    IMD_API_ENABLED: bool = True           # Enable IMD weather fetcher (may need IP whitelist)
    CWC_SCRAPER_ENABLED: bool = True       # Enable CWC flood forecast scraper
    TWITTER_BEARER_TOKEN: str = ""         # Twitter API v2 bearer token (optional)
    TELEGRAM_BOT_TOKEN: str = ""           # Telegram Bot API token (optional)

    # External Alerts Scheduler (minutes)
    ALERT_REFRESH_RSS_MINUTES: int = 15    # RSS feeds refresh interval
    ALERT_REFRESH_IMD_MINUTES: int = 60    # IMD refresh interval
    ALERT_REFRESH_TWITTER_MINUTES: int = 30  # Twitter refresh interval
    ALERT_REFRESH_CWC_MINUTES: int = 120   # CWC scraper refresh interval
    ALERT_REFRESH_TELEGRAM_MINUTES: int = 10  # PUB Telegram channel refresh interval

    # SendGrid Email Service (for email verification)
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@floodsafe.app"
    SENDGRID_FROM_NAME: str = "FloodSafe"

    # Email Verification
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24
    FRONTEND_URL: str = "http://localhost:5175"  # For verification redirects
    BACKEND_URL: str = "http://localhost:8000"   # For verification links in emails

    # Twilio WhatsApp/SMS Integration
    TWILIO_ACCOUNT_SID: str = ""                 # Starts with "AC..."
    TWILIO_AUTH_TOKEN: str = ""                  # Auth token from Twilio Console
    TWILIO_WHATSAPP_NUMBER: str = ""             # e.g., "whatsapp:+14155238886" (sandbox)
    TWILIO_SMS_NUMBER: str = ""                  # e.g., "+1234567890" (for SMS fallback)
    TWILIO_WEBHOOK_URL: str = ""                 # Your public webhook URL for signature validation
    TWILIO_TEST_PHONE: str = ""                  # Default recipient for test scripts (E.164, e.g. +919876543210)

    # Supabase Storage Configuration (for report photos)
    SUPABASE_URL: str = ""                        # e.g., "https://udblirsscaghsepuxxqv.supabase.co"
    SUPABASE_SERVICE_KEY: str = ""                # Service role key from Supabase Dashboard -> API
    SUPABASE_STORAGE_BUCKET: str = "report-photos"  # Bucket name for report photos

    # Wit.ai NLU (Meta) — Natural language understanding for WhatsApp bot
    WIT_AI_TOKEN: str = ""                         # Wit.ai Server Access Token
    WIT_AI_ENABLED: bool = True                    # Auto-disabled if WIT_AI_TOKEN is empty

    # Meta Llama API — AI-generated risk summaries
    META_LLAMA_API_KEY: str = ""                   # Meta Llama API key (llama.developer.meta.com)
    LLAMA_ENABLED: bool = True                     # Auto-disabled if no API key set
    LLAMA_API_URL: str = "https://api.llama.com/compat/v1"  # Meta Llama API (OpenAI-compatible)
    LLAMA_FALLBACK_URL: str = "https://api.groq.com/openai/v1"  # Groq free tier fallback
    LLAMA_FALLBACK_API_KEY: str = ""               # Groq API key (fallback)
    LLAMA_MODEL: str = "llama-3.3-8b"              # Model name for Meta API
    LLAMA_FALLBACK_MODEL: str = "llama-3.1-8b-instant"  # Model name for Groq

    # Meta WhatsApp Cloud API (parallel to Twilio)
    META_WHATSAPP_TOKEN: str = ""                  # Meta Graph API access token
    META_PHONE_NUMBER_ID: str = ""                 # WhatsApp Business phone number ID
    META_VERIFY_TOKEN: str = ""                    # Webhook verification token
    META_APP_SECRET: str = ""                      # App secret for signature validation
    META_WHATSAPP_ENABLED: bool = True             # Auto-disabled if META_WHATSAPP_TOKEN is empty

    # Google FloodHub Integration
    GOOGLE_FLOODHUB_API_KEY: str = ""             # Google Flood Forecasting API key (waitlist required)
    PUB_API_KEY: str = ""                          # Singapore PUB data.gov.sg API key (optional, for higher rate limits)
    NEA_API_KEY: str = ""                          # Singapore NEA weather API key (optional, for higher rate limits)
    OPENWEATHERMAP_API_KEY: str = ""               # OpenWeatherMap One Call 3.0 (Yogyakarta, free 1000/day)

    # Admin Panel Credentials (set via environment variables in production)
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD_HASH: str = ""  # bcrypt hash of admin password

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
