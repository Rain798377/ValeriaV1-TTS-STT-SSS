"""
LLM — Language Model via llama.cpp OpenAI-compatible server

Start your server with:
  llama-server -m Dolphin3.0-Llama3.2-3B-Q4_K_M.gguf --host 127.0.0.1 --port 8080 -ngl 99 -c 4096

  -ngl 99   = offload all layers — the 3B model fits fully on a 4GB GPU
  -c 4096   = context window

Input:  conversation history (list of {role, content} dicts)
Output: assistant response string
"""

import json
import urllib.request
import urllib.error

from config import Config


def get_llm_response(history: list[dict]) -> str:
    """
    Send conversation history to the llama.cpp server and return the response.
    History should be a list of {"role": "user"/"assistant", "content": "..."} dicts.
    """
    messages = [
        {"role": "system", "content": Config.SYSTEM_PROMPT},
        *history,
    ]

    payload = json.dumps({
        "messages":    messages,
        "max_tokens":  Config.LLM_MAX_TOKENS,
        "temperature": Config.LLM_TEMPERATURE,
        "stream":      False,
    }).encode("utf-8")

    url = f"{Config.LLAMA_API_URL}/v1/chat/completions"

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        content = data["choices"][0]["message"]["content"].strip()
        print(f"[LLM] Response: {content!r}")
        return content

    except urllib.error.URLError as e:
        print(f"[LLM] Connection error — is llama-server running? {e}")
        return "Sorry, I couldn't reach the language model right now."
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"[LLM] Parse error: {e}")
        return "I got a weird response from the language model."
    except Exception as e:
        print(f"[LLM] Unexpected error: {e}")
        return "Something went wrong on my end."
