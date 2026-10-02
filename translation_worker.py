"""Offline Argos translation subprocess isolated from the Qt screen monitor."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import OrderedDict, deque


MAX_CACHE_SIZE = 256


def find_translation_path(languages, source: str, target: str):
    by_code = {language.code: language for language in languages}
    if source not in by_code or target not in by_code:
        return []

    pending = deque([(source, [])])
    visited = {source}
    while pending:
        code, path = pending.popleft()
        for translation in by_code[code].translations_from:
            next_code = translation.to_lang.code
            next_path = [*path, translation]
            if next_code == target:
                return next_path
            if next_code not in visited:
                visited.add(next_code)
                pending.append((next_code, next_path))
    return []


class LocalSentenceSplitter:
    def split_sentences(self, text: str) -> list[str]:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+|\r?\n+", text.strip())
            if sentence.strip()
        ]
        return sentences or [text]


class OfflineTranslator:
    def __init__(self) -> None:
        import argostranslate.translate

        self.languages = argostranslate.translate.get_installed_languages()
        if not find_translation_path(self.languages, "en", "zh"):
            raise RuntimeError(
                "Offline Argos translation model is missing for en → zh. "
                "Run 'python setup_models.py' first."
            )
        self.cache: OrderedDict[str, str] = OrderedDict()

    def translate(self, text: str) -> str:
        key = hashlib.sha256(" ".join(text.split()).casefold().encode("utf-8")).hexdigest()
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]

        path = find_translation_path(self.languages, "en", "zh")
        if not path:
            raise RuntimeError("No installed offline Argos route from en to zh.")
        result = text
        for translation in path:
            model = translation
            while hasattr(model, "underlying"):
                model = model.underlying
            if not hasattr(model, "sentencizer"):
                raise RuntimeError("Installed Argos model has no sentence splitter.")
            model.sentencizer = LocalSentenceSplitter()
            result = translation.translate(result)

        self.cache[key] = result
        if len(self.cache) > MAX_CACHE_SIZE:
            self.cache.popitem(last=False)
        return result


def send_response(response: dict[str, object]) -> None:
    print(json.dumps(response, ensure_ascii=False), flush=True)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        translator = OfflineTranslator()
    except Exception as error:
        send_response({"error": str(error)})
        return 1

    send_response({"ready": True})
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("Request must be a JSON object.")
            if request.get("stop") is True:
                return 0
            text = request.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Request text must be a non-empty string.")
            send_response({"translation": translator.translate(text)})
        except Exception as error:
            send_response({"error": str(error)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
