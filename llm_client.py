import os, json, requests
from dotenv import load_dotenv
from contracts import MODEL_NAME, BASE_URL

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")


def ask(system: str, user: str, timeout: int = 20) -> dict:
    """Gọi model, trả dict. Lỗi thì trả {} — pipeline vẫn chạy tiếp."""
    try:
        r = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "model": MODEL_NAME,
                "temperature": 0,
                "max_tokens": 300,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=timeout,
        )
        txt = r.json()["choices"][0]["message"]["content"]
        txt = txt.replace("```json", "").replace("```", "").strip()
        return json.loads(txt)
    except Exception as e:
        return {"_error": str(e)}