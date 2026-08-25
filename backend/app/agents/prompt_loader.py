"""Loads prompt templates from app/agents/prompts/*.md — never inlined in
node code."""
from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"


@lru_cache
def load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text()
