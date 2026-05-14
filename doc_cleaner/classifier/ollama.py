from __future__ import annotations
import json
import re
from urllib.parse import urlparse
import httpx
from doc_cleaner.classifier.schema import ClassificationResult

_LOCALHOST = {"127.0.0.1", "localhost", "::1"}
_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def parse_classification(raw: str) -> ClassificationResult:
    """Parse raw Ollama response into ClassificationResult.
    Strips markdown fences. Returns Review result on any parse failure."""
    text = raw.strip()

    fence_match = _JSON_FENCE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        data = json.loads(text)
        return ClassificationResult.model_validate(data)
    except Exception:
        return ClassificationResult(
            category="Review",
            suggested_filename="",
            confidence=0,
            reason=f"Failed to parse model response: {raw[:200]}",
            needs_review=True,
        )


class OllamaClient:
    def __init__(
        self,
        host: str = "http://127.0.0.1:11434",
        model: str = "qwen3.5:9b",
        timeout: int = 120,
        allow_remote: bool = False,
    ):
        parsed = urlparse(host)
        if not allow_remote and parsed.hostname not in _LOCALHOST:
            raise ValueError(
                f"Non-localhost Ollama host '{host}' requires --allow-remote-ollama. "
                "This flag acknowledges that document content will leave this machine."
            )
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def generate(self, prompt: str) -> str:
        """POST to Ollama /api/generate and return the response string."""
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "think": False,
            "options": {"temperature": 0.1},
        }
        try:
            resp = self._client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")
        except httpx.ConnectError:
            raise ConnectionError(
                f"Ollama is not running at {self.host}.\n"
                "Start it with: ollama serve"
            )

    def classify(self, prompt: str) -> ClassificationResult:
        """Generate + parse. Retries once with a repair prompt on JSON parse failure."""
        raw = self.generate(prompt)
        result = parse_classification(raw)

        if result.category == "Review" and result.confidence == 0:
            repair_prompt = (
                "The following text is not valid JSON. "
                "Return ONLY the JSON object, no markdown, no explanation:\n"
                f"{raw[:500]}"
            )
            raw2 = self.generate(repair_prompt)
            result2 = parse_classification(raw2)
            if result2.category != "Review" or result2.confidence > 0:
                return result2

        return result

    def suggest_taxonomy(
        self,
        files: list[tuple[str, str]],
        existing: dict[str, list[str]] | None = None,
    ) -> dict[str, list[str]]:
        """Ask the model to suggest taxonomy additions based on filenames + text peeks.

        Each entry in files is (filename, peek_text). peek_text may be empty.
        If existing is provided, the model is asked to suggest ONLY additions that
        genuinely don't fit the existing structure.
        """
        lines = []
        for filename, peek in files[:200]:
            if peek:
                short = peek.replace("\n", " ").strip()[:150]
                lines.append(f"- {filename}: \"{short}\"")
            else:
                lines.append(f"- {filename}")
        files_text = "\n".join(lines)

        if existing:
            existing_text = "\n".join(
                f"- {cat}" + (f": {', '.join(subs)}" if subs else "")
                for cat, subs in existing.items()
                if cat not in ("Review", "Archiv", "Duplikate")
            )
            prompt = (
                "You are organizing personal documents into a folder structure.\n\n"
                f"EXISTING FOLDER STRUCTURE:\n{existing_text}\n\n"
                f"NEW DOCUMENTS:\n{files_text}\n\n"
                "Suggest ONLY new categories or subcategories that these documents genuinely need "
                "and that do not already fit the existing structure. "
                "Return {} if everything fits. Do not repeat existing entries.\n"
                "Return ONLY a valid JSON object with German category names as keys "
                "and arrays of German subcategory names as values.\n"
                'Example: {"Technik": ["Gerätehandbücher"]}'
            )
        else:
            prompt = (
                "You are organizing personal documents into a folder structure.\n"
                "Based on the filenames and content snippets below, suggest a 2-level folder taxonomy in German.\n\n"
                f"FILES:\n{files_text}\n\n"
                "Return ONLY a valid JSON object. Keys are top-level category names in German. "
                "Values are arrays of subcategory names in German (may be empty []).\n"
                "Use 5-10 broad categories. Do not create a category for just one file.\n"
                "Do not include Review or Archiv — those are added automatically.\n\n"
                'Example: {"Finanzen": ["Rechnungen", "Steuern"], "Wohnen": ["Miete"]}'
            )
        raw = self.generate(prompt)
        text = raw.strip()
        fence_match = _JSON_FENCE.search(text)
        if fence_match:
            text = fence_match.group(1).strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return {k: (v if isinstance(v, list) else []) for k, v in data.items()}
        except Exception:
            pass
        return {}

    def check_health(self) -> bool:
        try:
            resp = self._client.get(f"{self.host}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            resp = self._client.get(f"{self.host}/api/tags", timeout=10)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    def close(self) -> None:
        self._client.close()
