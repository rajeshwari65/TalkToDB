"""Environment and path helpers."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-mpnet-base-v2").strip()
TOP_K = int(os.getenv("TOP_K", "5"))
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SQL_DIR = ROOT / "sql"
POLICY_DIR = ROOT / "docs" / "policy_documents"


def groq_configured() -> bool:
    if not GROQ_API_KEY:
        return False
    lowered = GROQ_API_KEY.lower()
    return not lowered.startswith("gsk_your") and lowered not in {"changeme", "your_key_here"}


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")
