"""Discord 웹훅으로 알림 보내기"""
import time
from datetime import date, datetime

from .errors import SendError
from .http import Http, HttpError
from .model import Posting

BLUE = 0x2F6FED
RED = 0xE5484D           # 마감 3일 이내
URGENT_DAYS = 3
NO_MENTIONS = {"parse": []}   # 공고 제목에 @everyone 이 있어도 멘션이 울리지 않게


def deadline_text(deadline: date | None, today: date) -> str:
    if deadline is None:
        return "상시채용"
    days = (deadline - today).days
    return f"{deadline.month}/{deadline.day} ({'D-day' if days == 0 else f'D-{days}'})"


def education_text(limited: bool | None) -> str:
    return "확인 필요 (공고에서 직접 확인)" if limited is None else ("제한 있음" if limited else "제한 없음")


def build_embed(postings: list[Posting], now: datetime) -> dict:
    """같은 공고로 묶인 Posting 들 → Discord 카드 하나. 첫 번째 출처의 정보를 대표로 쓴다."""
    main = postings[0]
    today = now.date()
    urgent = main.deadline is not None and (main.deadline - today).days <= URGENT_DAYS
    links = " · ".join(f"[{p.source}]({p.url})" for p in postings)
    return {
        "title": main.title[:256],
        "url": main.url,
        "color": RED if urgent else BLUE,
        "fields": [
            {"name": "회사", "value": main.company or "-", "inline": True},
            {"name": "종류", "value": f"{main.kind} ({main.program_type})" if main.program_type else main.kind,
             "inline": True},
            {"name": "지역", "value": main.region or "-", "inline": True},
            {"name": "마감", "value": deadline_text(main.deadline, today), "inline": True},
            {"name": "학력", "value": education_text(main.education_limited), "inline": True},
            {"name": "링크", "value": links[:1024], "inline": False},
        ],
    }


class DiscordNotifier:
    def __init__(self, webhook_url: str, http: Http | None = None, retries: int = 3, sleep=time.sleep):
        self.webhook_url = webhook_url
        self.http = http or Http()
        self.retries = retries
        self.sleep = sleep

    def send_posting(self, postings: list[Posting], now: datetime) -> None:
        self._post({"username": "취업 공고 알림", "allowed_mentions": NO_MENTIONS,
                    "embeds": [build_embed(postings, now)]})
        self.sleep(1)    # 연속 전송 간격 (전송 제한 예방)

    def send_text(self, text: str) -> None:
        self._post({"username": "취업 공고 알림", "allowed_mentions": NO_MENTIONS, "content": text[:2000]})

    def _post(self, payload: dict) -> None:
        """전송. 429(너무 빠름)·5xx(Discord 쪽 문제)·연결 실패는 다시 시도하고,
        그 밖의 4xx(주소 잘못됨, 웹훅 삭제됨)는 다시 해도 같으므로 바로 실패 처리."""
        error = ""
        for attempt in range(1, self.retries + 1):
            try:
                self.http.post_json(self.webhook_url, payload)
                return
            except HttpError as e:
                error = f"HTTP {e.status}"
                if e.status == 429:
                    self.sleep(e.retry_after + 0.5)
                    continue
                if e.status < 500:
                    break
            except OSError as e:
                error = f"연결 실패 ({e.__class__.__name__})"
            if attempt < self.retries:
                self.sleep(2 * attempt)
        raise SendError(error)
