import json
import urllib.error
import urllib.request

from .QAModels import BaseQAModel
from .SummarizationModels import BaseSummarizationModel


class CodexProxyError(RuntimeError):
    pass


class CodexProxyClient:
    def __init__(
        self,
        base_url="http://localhost:11435/v1",
        model="gpt-5.5",
        api_key="codex-proxy",
        timeout=600,
        temperature=0,
        reasoning_effort=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.call_count = 0

    def chat(self, messages, max_tokens=None, response_format=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        if response_format is not None:
            payload["response_format"] = response_format

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        last_error = None
        for _ in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    self.call_count += 1
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = CodexProxyError(f"codex-proxy HTTP {exc.code}: {detail}")
            except urllib.error.URLError as exc:
                last_error = CodexProxyError(f"codex-proxy request failed: {exc}")
        else:
            raise last_error

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise CodexProxyError(f"Unexpected codex-proxy response: {data}") from exc

    def health(self):
        health_url = self.base_url.rsplit("/", 1)[0] + "/health"
        try:
            with urllib.request.urlopen(health_url, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise CodexProxyError(f"codex-proxy health check failed: {exc}") from exc


class CodexProxySummarizationModel(BaseSummarizationModel):
    def __init__(self, client=None, **client_kwargs):
        self.client = client or CodexProxyClient(**client_kwargs)

    def summarize(self, context, max_tokens=500):
        messages = [
            {
                "role": "system",
                "content": "You summarize Korean patent texts faithfully and concisely.",
            },
            {
                "role": "user",
                "content": (
                    "다음 특허 요약 묶음을 근거에 없는 내용 없이 핵심 기술, 목적, "
                    "구성 요소, 효과 중심으로 한국어로 요약하세요.\n\n"
                    f"{context}"
                ),
            },
        ]
        return self.client.chat(messages, max_tokens=max_tokens).strip()


class CodexProxyQAModel(BaseQAModel):
    def __init__(self, client=None, **client_kwargs):
        self.client = client or CodexProxyClient(**client_kwargs)

    def answer_question(self, context, question):
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a patent QA reader. Answer only from the provided context. "
                    "If the context is insufficient, say that it is insufficient."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion:\n{question}\n\nAnswer in Korean.",
            },
        ]
        return self.client.chat(messages, max_tokens=350).strip()


def parse_json_object(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise
