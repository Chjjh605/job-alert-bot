"""바깥과 HTTP 로 주고받는 부분만 모아 둔 곳 (테스트에서는 가짜로 바꿔 끼운다)

오류 메시지에 요청 주소를 넣지 않는다. 주소에 API 키·웹훅 토큰이 들어 있기 때문.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
BOT_UA = "jobalert/0.1 (personal job alert bot)"


class HttpError(Exception):
    def __init__(self, status: int, retry_after: float = 0.0):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.retry_after = retry_after    # 429(전송 제한)일 때 기다리라고 한 초


def _retry_after(e: urllib.error.HTTPError) -> float:
    try:
        return float(json.loads(e.read() or b"{}").get("retry_after", 1))
    except (ValueError, AttributeError):
        return 1.0


class Http:
    def __init__(self, timeout: float = 20):
        self.timeout = timeout

    def _open(self, req: urllib.request.Request) -> str:
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            raise HttpError(e.code, _retry_after(e) if e.code == 429 else 0.0) from None

    def get_text(self, url: str) -> str:
        return self._open(urllib.request.Request(url, headers={"User-Agent": BOT_UA}))

    def post_form(self, url: str, form: dict) -> str:
        data = urllib.parse.urlencode(form).encode("utf-8")
        return self._open(urllib.request.Request(url, data=data, headers={"User-Agent": BROWSER_UA}))

    def post_json(self, url: str, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._open(urllib.request.Request(url, data=body, method="POST", headers={
            "Content-Type": "application/json; charset=utf-8", "User-Agent": BOT_UA}))
