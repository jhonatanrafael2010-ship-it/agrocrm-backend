import os
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional


SKILLS_DIR = Path(__file__).parent / "skills"

# Cache de skills (carregadas uma vez, ficam em memória)
_skills_cache: Dict[str, str] = {}


def load_skill(skill_name: str) -> Optional[str]:
    """Carrega skill do disco com cache em memória."""
    if skill_name in _skills_cache:
        return _skills_cache[skill_name]

    path = SKILLS_DIR / skill_name / "SKILL.md"
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    _skills_cache[skill_name] = content
    return content


def invalidate_skills_cache() -> None:
    """Limpa cache de skills. Chamar após editar SKILL.md em dev."""
    _skills_cache.clear()


def list_skills_metadata() -> Dict[str, str]:
    metadata = {}
    if not SKILLS_DIR.exists():
        return metadata
    for skill_folder in SKILLS_DIR.iterdir():
        skill_file = skill_folder / "SKILL.md"
        if not skill_file.exists():
            continue
        content = skill_file.read_text(encoding="utf-8")
        match = re.search(r"description:\s*(.+)", content)
        if match:
            metadata[skill_folder.name] = match.group(1).strip()
    return metadata


def _call_openai_with_retry(client, messages, max_retries: int = 3) -> str:
    """Chama OpenAI com retry e exponential backoff."""
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                time.sleep(wait_time)
    raise last_error


def interpret_with_skill(
    message_text: str,
    skill_name: str,
    current_state: str = "",
) -> Optional[Dict[str, Any]]:
    if not os.getenv("OPENAI_API_KEY"):
        return None

    skill_content = load_skill(skill_name)
    if not skill_content:
        return None

    try:
        from openai import OpenAI
        client = OpenAI()

        system_prompt = (
            skill_content
            + "\n\nResponda APENAS com JSON válido. Sem markdown, sem comentários."
        )

        user_prompt = (
            f"Estado atual: {current_state or 'none'}\n"
            f"Mensagem: {message_text}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        output = _call_openai_with_retry(client, messages)
        if not output:
            return None

        try:
            return json.loads(output)
        except Exception:
            match = re.search(r"\{.*\}", output, flags=re.DOTALL)
            if not match:
                return None
            return json.loads(match.group(0))

    except Exception as e:
        print(f"[SkillLoader] erro: {e}")
        return None
