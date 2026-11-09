"""경계 ②: 출처별 변환 — 청년일경험 포털

tests/fixtures/youth_work_it_list.html 은 2026-11-09 에 실제로 받은 IT 직무 목록 페이지다.
"""
from datetime import date
from pathlib import Path

import pytest

from jobalert.errors import SourceError
from jobalert.sources.youth_work import YouthWorkSource

FIXTURE = (Path(__file__).parent / "fixtures" / "youth_work_it_list.html").read_text(encoding="utf-8")


class 가짜HTTP:
    def __init__(self, *응답들):
        self.응답들 = list(응답들)
        self.요청들: list[dict] = []

    def post_form(self, url, form):
        self.요청들.append(form)
        return self.응답들.pop(0)


def test_목록_페이지의_공고를_모두_가져온다():
    공고들 = YouthWorkSource(http=가짜HTTP(FIXTURE)).fetch()

    assert len(공고들) == 24


def test_공고_카드에서_회사명_마감일_지역_링크를_읽는다():
    첫공고 = YouthWorkSource(http=가짜HTTP(FIXTURE)).fetch()[0]

    assert 첫공고.source == "청년일경험"
    assert 첫공고.source_id == "PG0031152202611090001"
    assert 첫공고.title == "[넥스트씨아이씨코리아]DevOps 기반 CI/CD 파이프라인 구축 및 자동화 실무 일경험"
    assert 첫공고.company == "유한회사 넥스트씨아이코리아"
    assert 첫공고.kind == "일경험"
    assert 첫공고.region == "경기"
    assert 첫공고.job_field == "IT"
    assert 첫공고.deadline == date(2026, 11, 15)
    assert 첫공고.url == "https://yw.work24.go.kr/d/a/prgmDtl/2e0t00Lcpq"
    assert 첫공고.education_limited is None     # 목록에 학력 정보가 없음
    assert 첫공고.program_type == "인턴형"


def test_일경험_유형을_구분해서_읽는다():
    공고들 = YouthWorkSource(http=가짜HTTP(FIXTURE)).fetch()

    유형별 = {}
    for p in 공고들:
        유형별[p.program_type] = 유형별.get(p.program_type, 0) + 1

    assert 유형별 == {"인턴형": 17, "프로젝트형": 6, "ESG지원형": 1}


def test_IT_직무만_최근_모집순으로_요청한다():
    http = 가짜HTTP(FIXTURE)

    YouthWorkSource(http=http).fetch()

    assert http.요청들[0]["dtyCd"] == "14"         # 14 = IT
    assert http.요청들[0]["sortOption"] == "C"     # C = 최근모집일순


def test_한_페이지가_가득_차면_다음_페이지도_가져온다():
    빈페이지 = '<html><ul class="card-list "></ul></html>'
    http = 가짜HTTP(FIXTURE, 빈페이지)

    공고들 = YouthWorkSource(http=http, page_size=24).fetch()   # 첫 페이지 24건 = 가득 참

    assert [요청["currentPageNo"] for 요청 in http.요청들] == ["1", "2"]
    assert len(공고들) == 24


def test_목록_구조를_못_찾으면_사이트가_바뀐_것으로_보고_수집_실패로_알린다():
    with pytest.raises(SourceError, match="목록"):
        YouthWorkSource(http=가짜HTTP("<html><body>점검 중입니다</body></html>")).fetch()


def test_연결이_안_되면_수집_실패로_알리고_원인을_적는다():
    import urllib.error

    class 끊기는HTTP:
        def post_form(self, url, form):
            raise urllib.error.URLError(ConnectionResetError(104, "Connection reset by peer"))

    with pytest.raises(SourceError, match="Connection reset by peer"):
        YouthWorkSource(http=끊기는HTTP()).fetch()
