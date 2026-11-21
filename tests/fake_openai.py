# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""A fake OpenAI-compatible backend for trying the interface without a model.

    python tests/fake_openai.py --port 8999 --delay 0.5

then start stt-to-script with ``STT_TO_SCRIPT_API_BASE_URL=http://127.0.0.1:8999/v1``
and ``STT_TO_SCRIPT_MODEL=fake``. Every answer starts with a reasoning block (to
exercise the filter) followed by the input text, prefixed with the name of
the pass, so that the effect of each step is visible.

Uses FastAPI and uvicorn, which Gradio already depends on.
"""

from __future__ import annotations

import argparse
import asyncio

import uvicorn
from fastapi import FastAPI, Request

MARKERS = ("Ab hier kommt der zu bearbeitende Text:\n", "The text to edit follows from here:\n")


def create_app(delay: float = 0.0) -> FastAPI:
    app = FastAPI()

    @app.get("/v1/models")
    async def models():
        return {"object": "list", "data": [{"id": "fake", "object": "model"}]}

    @app.post("/v1/chat/completions")
    async def completions(request: Request):
        body = await request.json()
        prompt = body["messages"][0]["content"]
        text = prompt
        for marker in MARKERS:
            if marker in prompt:
                text = prompt.split(marker, 1)[1].strip()
        if "Markdown" in prompt and "RAG" not in prompt:
            text = "## Abschnitt\n\n" + text
        await asyncio.sleep(delay)
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": f"<think>fake reasoning</think>\n{text}",
                    },
                    "finish_reason": "stop",
                }
            ]
        }

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=8999)
    parser.add_argument("--delay", type=float, default=0.0, help="seconds per request")
    args = parser.parse_args()
    uvicorn.run(create_app(args.delay), host="127.0.0.1", port=args.port, log_level="warning")
