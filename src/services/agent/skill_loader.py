import os
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


SKILLS_DIR = Path(__file__).parent / "skills"


def load_skill(skill_name: str) -> Optional[str]:
    path = SKILLS_DIR / skill_name / "SKILL.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


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

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        output = (response.output_text or "").strip()
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
