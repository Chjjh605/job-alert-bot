"""경계 ③: Discord 전송 — 공고 → Discord 로 가는 메시지"""
from datetime import date, datetime, timedelta, timezone

import pytest

from jobalert.discord import DiscordNotifier
from jobalert.errors import SendError
from jobalert.http import HttpError
from jobalert.model import Posting

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 10, 9, 0, tzinfo=KST)
WEBHOOK = "https://discord.test/api/webhooks/1/token"


def 공고(**바꿀값):
    값 = dict(source="청년일경험", source_id="PG001", company="구름테크",
             title="클라우드 인프라 운영 인턴", kind="일경험", region="서울",
             job_field="IT", deadline=date(2026, 11, 20), url="https://example.test/PG001",
             program_type="인턴형")
    값.update(바꿀값)
    return Posting(**값)


class 가짜HTTP:
    def __init__(self, *실패들):
        self.실패들 = list(실패들)     # 차례대로 던질 오류 (없으면 성공)
        self.보낸것: list[dict] = []

    def post_json(self, url, payload):
        if self.실패들:
            raise self.실패들.pop(0)
        self.보낸것.append(payload)


def 보내기(postings, http=None, now=NOW):
    http = http or 가짜HTTP()
    기다린초: list[float] = []
    DiscordNotifier(WEBHOOK, http=http, sleep=기다린초.append).send_posting(postings, now)
    return http, 기다린초


def 카드(http):
    return http.보낸것[0]["embeds"][0]


def 항목(http):
    return {f["name"]: f["value"] for f in 카드(http)["fields"]}


def test_알림에_회사명_종류_지역_마감일과_D_day가_들어간다():
    http, _ = 보내기([공고()])

    assert 카드(http)["title"] == "클라우드 인프라 운영 인턴"
    assert 항목(http)["회사"] == "구름테크"
    assert 항목(http)["종류"] == "일경험 (인턴형)"
    assert 항목(http)["지역"] == "서울"
    assert 항목(http)["마감"] == "11/20 (D-10)"


def test_같은_공고가_여러_출처에_있으면_출처별_링크를_모두_넣는다():
    http, _ = 보내기([공고(), 공고(source="잡알리오", url="https://example.test/J77")])

    assert 카드(http)["url"] == "https://example.test/PG001"
    assert 항목(http)["링크"] == "[청년일경험](https://example.test/PG001) · [잡알리오](https://example.test/J77)"


@pytest.mark.parametrize("마감일, 빨강", [
    (date(2026, 11, 13), True),    # D-3
    (date(2026, 11, 14), False),   # D-4
])
def test_마감이_3일_이내면_빨간색으로_표시한다(마감일, 빨강):
    http, _ = 보내기([공고(deadline=마감일)])

    assert (카드(http)["color"] == 0xE5484D) is 빨강


def test_오늘_마감은_D_day로_상시채용은_상시로_보여준다():
    오늘, _ = 보내기([공고(deadline=date(2026, 11, 10))])
    상시, _ = 보내기([공고(deadline=None)])

    assert 항목(오늘)["마감"] == "11/10 (D-day)"
    assert 항목(상시)["마감"] == "상시채용"


def test_출처가_학력_정보를_주지_않으면_학력_확인_필요라고_적는다():
    http, _ = 보내기([공고(education_limited=None)])

    assert 항목(http)["학력"] == "확인 필요 (공고에서 직접 확인)"


def test_공고_제목에_everyone이_있어도_전체_멘션이_울리지_않는다():
    http, _ = 보내기([공고(title="@everyone 클라우드 인턴")])

    assert http.보낸것[0]["allowed_mentions"] == {"parse": []}


def test_전송_제한_429를_받으면_기다렸다가_다시_보낸다():
    http, 기다린초 = 보내기([공고()], http=가짜HTTP(HttpError(429, retry_after=2.0)))

    assert len(http.보낸것) == 1
    assert 기다린초 and 기다린초[0] >= 2.0


def test_웹훅_주소가_잘못됐으면_다시_시도하지_않고_전송_실패로_알린다():
    http = 가짜HTTP(HttpError(404), HttpError(404), HttpError(404))

    with pytest.raises(SendError, match="404"):
        보내기([공고()], http=http)
    assert len(http.실패들) == 2      # 한 번만 시도함


def test_오류_메시지에_웹훅_주소가_노출되지_않는다():
    with pytest.raises(SendError) as 오류:
        보내기([공고()], http=가짜HTTP(HttpError(500), HttpError(500), HttpError(500)))

    assert "token" not in str(오류.value)


def test_수집_실패_알림은_글로_보낸다():
    http = 가짜HTTP()

    DiscordNotifier(WEBHOOK, http=http, sleep=lambda s: None).send_text("⚠️ 수집 실패 알림")

    assert http.보낸것[0]["content"] == "⚠️ 수집 실패 알림"
    assert http.보낸것[0]["allowed_mentions"] == {"parse": []}
