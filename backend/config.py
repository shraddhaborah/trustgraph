"""Central configuration. Import this everywhere instead of calling os.getenv inline.

Loading happens once, at import, from a .env file that is NOT committed. This is
what stops the "I restarted uvicorn in a new tab and lost the API key" failure
mode -- the key no longer depends on which terminal you happened to export it in.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

# --- Temporal ---------------------------------------------------------------
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "trust-queue")

# --- Anthropic --------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Current model ids: claude-opus-5, claude-sonnet-5, claude-sonnet-4-6, claude-haiku-4-5.
# Sonnet 4.6 is a good cost/quality point for structured extraction.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "8000"))

# --- Demo mode --------------------------------------------------------------
# When true, the extraction activity returns a fixture instead of calling Claude.
# Lets anyone clone the repo and see the full pipeline run with no API key.
# Auto-enables when no key is present, so the app never dies with a config error.
DEMO_MODE = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes") or not ANTHROPIC_API_KEY

# --- Ingestion tuning -------------------------------------------------------
# Temporal payloads are capped (~2MB per payload, 4MB gRPC message). Never put
# raw PDF bytes in a workflow argument -- we stage the file on disk and pass a path.
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/trustgraph_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))  # 25 MB
# Characters of extracted text sent to the model per extraction call.
CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "60000"))
CHUNK_OVERLAP_CHARS = int(os.getenv("CHUNK_OVERLAP_CHARS", "2000"))

CORS_ORIGINS = [o for o in os.getenv("CORS_ORIGINS", "*").split(",") if o]