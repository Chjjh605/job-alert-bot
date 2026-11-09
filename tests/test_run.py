"""경계 ①: 한 번의 실행

출처(사이트)와 Discord 는 가짜로 바꿔 끼우고, 기록 파일은 진짜 임시 파일을 쓴다.
"""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from jobalert.errors import SendError, SourceError
from jobalert.model import InterestConditions, Posting
from jobalert.run import run_once

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 10, 9, 0, tzinfo=KST)          # 화요일 오전 9시 실행

CONDITIONS = InterestConditions(
    job_keywords=["클라우드", "인프라", "서버"],
    kinds=["인턴", "일경험", "신입"],
    regions=["서울", "경기", "인천"],
    exclude_keywords=["경력", "시니어", "영업"],
    program_types=["인턴형"],
)


def 공고(**바꿀값) -> Posting:
    """관심 조건에 맞는 기본 공고. 테스트마다 필요한 값만 바꿔 쓴다."""
    기본 = Posting(
        source="청년일경험", source_id="PG001", company="구름테크",
        title="클라우드 인프라 운영 인턴", kind="인턴", region="서울 강남구",
        job_field="IT·SW", deadline=date(2026, 11, 20),
        url="https://example.test/PG001", program_type="인턴형",
    )
    return replace(기본, **바꿀값)


class 가짜출처:
    def __init__(self, name, postings=(), error=None):
        self.name = name
        self._postings = list(postings)
        self._error = error

    def fetch(self):
        if self._error:
            raise self._error
        return list(self._postings)


class 가짜디스코드:
    def __init__(self, 고장=False):
        self.고장 = 고장
        self.보낸공고: list[list[Posting]] = []   # 알림 한 건 = 같은 공고로 묶인 Posting 목록
        self.보낸글: list[str] = []
        self.마감임박: list[list[str]] = []      # 마감 임박 알림 한 건 = 공고 제목 목록

    def send_posting(self, postings, now):
        if self.고장:
            raise SendError("HTTP 500")
        self.보낸공고.append(list(postings))

    def send_text(self, text):
        self.보낸글.append(text)

    def send_deadline_reminder(self, groups, now):
        if self.고장:
            raise SendError("HTTP 500")
        self.마감임박.append([group[0].title for group in groups])

    def 알림제목(self):
        return [group[0].title for group in self.보낸공고]


def 실행(출처들, 디스코드, tmp_path, now=NOW):
    return run_once(출처들, 디스코드, tmp_path / "state.json", CONDITIONS, now)


def test_관심_조건에_맞는_공고는_알림이_가고_직무가_다른_공고는_안_간다(tmp_path):
    디스코드 = 가짜디스코드()
    출처 = 가짜출처("청년일경험", [
        공고(),
        공고(source_id="PG002", title="광고 마케팅 직무체험", job_field="광고·마케팅"),
    ])

    실행([출처], 디스코드, tmp_path)

    assert 디스코드.알림제목() == ["클라우드 인프라 운영 인턴"]


@pytest.mark.parametrize("이유, 바꿀값", [
    ("지역이 멂", {"region": "부산 해운대구"}),
    ("제외 키워드", {"title": "클라우드 엔지니어 (경력 3년 이상)"}),
    ("학력 제한", {"education_limited": True}),
    ("공고 종류가 다름", {"kind": "경력"}),
    ("이미 마감됨", {"deadline": date(2026, 11, 9)}),
    ("지역무관 (지역 목록에 없음)", {"region": "지역무관"}),
    ("관심 없는 일경험 유형", {"program_type": "프로젝트형"}),
])
def test_제외_조건에_걸리는_공고는_알림이_가지_않는다(tmp_path, 이유, 바꿀값):
    디스코드 = 가짜디스코드()

    실행([가짜출처("청년일경험", [공고(**바꿀값)])], 디스코드, tmp_path)

    assert 디스코드.알림제목() == [], 이유


@pytest.mark.parametrize("이유, 바꿀값", [
    ("일경험 유형이 없는 출처", {"program_type": ""}),
    ("상시채용", {"deadline": None}),
    ("학력 정보 없음", {"education_limited": None}),
    ("오늘 마감", {"deadline": date(2026, 11, 10)}),
])
def test_조건을_확인할_수_없거나_경계에_있는_공고는_놓치지_않고_보낸다(tmp_path, 이유, 바꿀값):
    디스코드 = 가짜디스코드()

    실행([가짜출처("청년일경험", [공고(**바꿀값)])], 디스코드, tmp_path)

    assert 디스코드.알림제목() == ["클라우드 인프라 운영 인턴"], 이유


def test_여러_출처에_올라온_같은_공고는_출처를_묶어_한_번만_알린다(tmp_path):
    디스코드 = 가짜디스코드()
    청년 = 가짜출처("청년일경험", [공고()])
    알리오 = 가짜출처("잡알리오", [공고(source="잡알리오", source_id="J77",
                                    title="클라우드  인프라 운영 인턴 ",   # 띄어쓰기만 다름
                                    url="https://example.test/J77")])

    실행([청년, 알리오], 디스코드, tmp_path)

    assert [[p.source for p in 묶음] for 묶음 in 디스코드.보낸공고] == [["청년일경험", "잡알리오"]]


def test_이미_알림을_보낸_공고는_다음_실행에서_다시_보내지_않는다(tmp_path):
    출처 = 가짜출처("청년일경험", [공고()])
    실행([출처], 가짜디스코드(), tmp_path)

    두번째 = 가짜디스코드()
    실행([출처], 두번째, tmp_path, now=NOW + timedelta(hours=9))

    assert 두번째.알림제목() == []


def test_마감된_공고가_다시_올라오면_재공고로_보고_다시_알린다(tmp_path):
    실행([가짜출처("청년일경험", [공고(deadline=date(2026, 11, 20))])], 가짜디스코드(), tmp_path)

    한달뒤 = 가짜디스코드()
    재공고 = 공고(source_id="PG999", deadline=date(2026, 12, 24))
    실행([가짜출처("청년일경험", [재공고])], 한달뒤, tmp_path, now=NOW + timedelta(days=30))

    assert 한달뒤.알림제목() == ["클라우드 인프라 운영 인턴"]


def test_마감_전에_같은_공고가_한_번_더_올라오면_다시_보내지_않는다(tmp_path):
    실행([가짜출처("청년일경험", [공고(deadline=date(2026, 11, 20))])], 가짜디스코드(), tmp_path)

    다음날 = 가짜디스코드()
    마감연장 = 공고(source_id="PG999", deadline=date(2026, 11, 27))
    실행([가짜출처("청년일경험", [마감연장])], 다음날, tmp_path, now=NOW + timedelta(days=1))

    assert 다음날.알림제목() == []


def test_보낸_공고_기록에는_제목과_회사명이_남지_않는다(tmp_path):
    실행([가짜출처("청년일경험", [공고()])], 가짜디스코드(), tmp_path)

    기록 = (tmp_path / "state.json").read_text(encoding="utf-8")

    assert "구름테크" not in 기록 and "클라우드" not in 기록


def test_출처_하나가_실패하면_수집_실패_알림을_보내고_다른_출처는_계속_수집한다(tmp_path):
    디스코드 = 가짜디스코드()
    고장난출처 = 가짜출처("청년일경험", error=SourceError("HTTP 503"))
    알리오 = 가짜출처("잡알리오", [공고(source="잡알리오", source_id="J77")])

    결과 = 실행([고장난출처, 알리오], 디스코드, tmp_path)

    assert 디스코드.알림제목() == ["클라우드 인프라 운영 인턴"]
    assert len(디스코드.보낸글) == 1
    assert "청년일경험" in 디스코드.보낸글[0] and "HTTP 503" in 디스코드.보낸글[0]
    assert not 결과.ok


def test_디스코드_전송에_실패한_공고는_다음_실행에서_다시_보낸다(tmp_path):
    출처 = 가짜출처("청년일경험", [공고()])
    결과 = 실행([출처], 가짜디스코드(고장=True), tmp_path)

    다음 = 가짜디스코드()
    실행([출처], 다음, tmp_path, now=NOW + timedelta(hours=9))

    assert not 결과.ok
    assert 다음.알림제목() == ["클라우드 인프라 운영 인턴"]


def test_문제가_없으면_실행_결과가_정상이다(tmp_path):
    결과 = 실행([가짜출처("청년일경험", [공고()])], 가짜디스코드(), tmp_path)

    assert 결과.ok


# ---------------------------------------------------------------- 마감 임박 알림
내일마감 = 공고(source_id="PG010", title="서버 운영 인턴", deadline=date(2026, 11, 11))
다음주마감 = 공고(source_id="PG011", title="클라우드 인턴", deadline=date(2026, 11, 17))
전날밤 = NOW - timedelta(hours=15)        # 11/9 18:00


def test_하루_첫_실행에서_알림을_보냈던_공고_중_내일_마감인_것을_모아_알린다(tmp_path):
    출처 = 가짜출처("청년일경험", [내일마감, 다음주마감])
    실행([출처], 가짜디스코드(), tmp_path, now=전날밤)

    아침 = 가짜디스코드()
    실행([출처], 아침, tmp_path, now=NOW)            # 11/10 09:00, 내일 = 11/11

    assert 아침.마감임박 == [["서버 운영 인턴"]]


def test_마감_임박_알림은_같은_날_두_번_보내지_않는다(tmp_path):
    출처 = 가짜출처("청년일경험", [내일마감])
    실행([출처], 가짜디스코드(), tmp_path, now=전날밤)
    실행([출처], 가짜디스코드(), tmp_path, now=NOW)

    저녁 = 가짜디스코드()
    실행([출처], 저녁, tmp_path, now=NOW + timedelta(hours=9))

    assert 저녁.마감임박 == []


def test_이번_실행에서_처음_알린_공고는_마감_임박_알림에_넣지_않는다(tmp_path):
    디스코드 = 가짜디스코드()

    실행([가짜출처("청년일경험", [내일마감])], 디스코드, tmp_path, now=NOW)

    assert 디스코드.알림제목() == ["서버 운영 인턴"]     # 새 공고 알림에 이미 D-1 로 보임
    assert 디스코드.마감임박 == []


def test_마감_임박_알림을_못_보내면_다음_실행에서_다시_보낸다(tmp_path):
    출처 = 가짜출처("청년일경험", [내일마감])
    실행([출처], 가짜디스코드(), tmp_path, now=전날밤)
    실행([출처], 가짜디스코드(고장=True), tmp_path, now=NOW)

    저녁 = 가짜디스코드()
    실행([출처], 저녁, tmp_path, now=NOW + timedelta(hours=9))

    assert 저녁.마감임박 == [["서버 운영 인턴"]]
