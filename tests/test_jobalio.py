"""경계 ②: 출처별 변환 — 잡알리오 (공공기관 채용정보 Open API)

tests/fixtures/jobalio_intern_list.json 은 2026-11-09 에 실제로 받은 '진행 중인 체험형 청년인턴' 목록이다.
"""
import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from jobalert.errors import SourceError
from jobalert.http import HttpError
from jobalert.sources.jobalio import JobAlioSource

FIXTURE = (Path(__file__).parent / "fixtures" / "jobalio_intern_list.json").read_text(encoding="utf-8")
KEY = "테스트용-키-ABC"


class 가짜HTTP:
    def __init__(self, *응답들):
        self.응답들 = list(응답들)
        self.요청들: list[dict] = []

    def get_text(self, url):
        self.요청들.append({k: v[0] for k, v in parse_qs(urlparse(url).query).items()})
        응답 = self.응답들.pop(0)
        if isinstance(응답, Exception):
            raise 응답
        return 응답


def 가져오기(*응답들, **옵션):
    http = 가짜HTTP(*응답들)
    return JobAlioSource(KEY, http=http, **옵션).fetch(), http


def 응답_바꾸기(바꿀함수) -> str:
    data = json.loads(FIXTURE)
    바꿀함수(data)
    return json.dumps(data, ensure_ascii=False)


def test_진행_중인_체험형_청년인턴만_요청한다():
    _, http = 가져오기(FIXTURE)

    요청 = http.요청들[0]
    assert (요청["hireTypeLst"], 요청["ongoingYn"], 요청["resultType"]) == ("R1060", "Y", "json")


def test_목록의_공고를_모두_가져온다():
    공고들, _ = 가져오기(FIXTURE)

    assert len(공고들) == 43


def test_공고에서_기관명_제목_마감일_지역_직무_링크를_읽는다():
    공고들, _ = 가져오기(FIXTURE)
    첫공고 = 공고들[0]

    assert 첫공고.source == "잡알리오"
    assert 첫공고.source_id == "306840"
    assert 첫공고.company == "한국보훈복지의료공단"
    assert 첫공고.title == "[부산보훈병원] 청년인턴(체험형-장애) 긴급채용공고"
    assert 첫공고.kind == "인턴"
    assert 첫공고.region == "부산"
    assert 첫공고.job_field == "보건.의료"
    assert 첫공고.deadline == date(2026, 11, 19)
    assert 첫공고.url == "https://job.alio.go.kr/recruitview.do?idx=306840"


@pytest.mark.parametrize("학력조건, 제한", [
    ("학력무관", False),
    ("고졸,대졸(2~3년),대졸(4년)", False),     # 모집 분야 중 하나라도 고졸 가능
    ("학력무관,대졸(4년)", False),
    ("대졸(4년)", True),
    ("대졸(2~3년),대졸(4년),석사,박사", True),
    ("", None),                                 # 학력 정보 없음 → 확인 못 함
])
def test_학력무관이나_고졸이_하나라도_있으면_지원_가능으로_본다(학력조건, 제한):
    def 바꾸기(data):
        data["result"][0]["acbgCondNmLst"] = 학력조건

    공고들, _ = 가져오기(응답_바꾸기(바꾸기))

    assert 공고들[0].education_limited is 제한


def test_전체_건수가_한_페이지보다_많으면_다음_페이지도_가져온다():
    def 첫페이지(data):
        data["totalCount"] = 60
        data["result"] = data["result"][:30]

    def 둘째페이지(data):
        data["totalCount"] = 60
        data["result"] = data["result"][30:]

    공고들, http = 가져오기(응답_바꾸기(첫페이지), 응답_바꾸기(둘째페이지), page_size=30)

    assert [요청["pageNo"] for 요청 in http.요청들] == ["1", "2"]
    assert len(공고들) == 43


def test_인증키_오류처럼_JSON이_아닌_응답이_오면_수집_실패로_알린다():
    xml = "<OpenAPI_ServiceResponse><cmmMsgHeader><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg></cmmMsgHeader></OpenAPI_ServiceResponse>"

    with pytest.raises(SourceError, match="SERVICE_KEY_IS_NOT_REGISTERED_ERROR"):
        가져오기(xml)


def test_API가_오류_코드를_보내면_수집_실패로_알린다():
    with pytest.raises(SourceError, match="잘못된 요청"):
        가져오기('{"resultCode": 10, "resultMsg": "잘못된 요청 파라미터 에러", "totalCount": 0, "result": []}')


def test_오류_메시지에_인증키가_노출되지_않는다():
    with pytest.raises(SourceError) as 오류:
        가져오기(HttpError(500))

    assert KEY not in str(오류.value)
