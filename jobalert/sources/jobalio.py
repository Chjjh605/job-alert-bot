"""잡알리오: 공공기관 채용정보 조회서비스 (공공데이터포털 Open API, data.go.kr 15125273)

공공기관 채용 공고 중 '진행 중인 체험형 청년인턴'만 요청한다(직무는 가리지 않음).
목록에 학력 조건이 있어서 학력 제한을 판단할 수 있다.
인증키는 요청 주소에 들어가므로 오류 메시지에 주소를 넣지 않는다.
"""
import json
import urllib.parse
from datetime import date

from ..errors import SourceError
from ..http import Http, HttpError
from ..model import Posting

LIST_URL = "https://apis.data.go.kr/1051000/recruitment/list"
DETAIL_URL = "https://job.alio.go.kr/recruitview.do?idx={}"
HIRE_TYPE_YOUTH_INTERN = "R1060"           # 고용유형: 청년인턴(체험형)
OK = 200
NO_EDUCATION_LIMIT = ("학력무관", "고졸")    # 이 중 하나라도 있으면 지원 가능


def education_limited(conditions: str) -> bool | None:
    """학력조건명목록 → 학력 제한 여부. 모집 분야가 여러 개면 하나라도 학력무관·고졸이면 지원 가능."""
    names = [n.strip() for n in conditions.split(",") if n.strip()]
    if not names:
        return None
    return not any(n in NO_EDUCATION_LIMIT for n in names)


def _ymd(text: str) -> date | None:
    text = (text or "").strip()
    return date(int(text[:4]), int(text[4:6]), int(text[6:8])) if len(text) == 8 and text.isdigit() else None


def parse_page(text: str) -> tuple[list[Posting], int]:
    """응답 본문 → (공고 목록, 전체 건수)"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 인증키 오류 등은 JSON 대신 XML 로 옴. 본문에는 인증키가 들어 있지 않다.
        raise SourceError(f"JSON이 아닌 응답 (인증키 확인 필요): {text[:200]}") from None
    if data.get("resultCode") != OK:
        raise SourceError(f"API 오류 {data.get('resultCode')}: {data.get('resultMsg', '')}")

    postings = []
    for item in data.get("result") or []:
        sn = str(item.get("recrutPblntSn", ""))
        postings.append(Posting(
            source="잡알리오",
            source_id=sn,
            company=(item.get("instNm") or "").strip(),
            title=" ".join((item.get("recrutPbancTtl") or "").split()),
            kind="인턴",
            region=item.get("workRgnNmLst") or "",
            job_field=item.get("ncsCdNmLst") or "",
            deadline=_ymd(item.get("pbancEndYmd")),
            url=DETAIL_URL.format(sn),
            education_limited=education_limited(item.get("acbgCondNmLst") or ""),
        ))
    return postings, int(data.get("totalCount") or 0)


class JobAlioSource:
    name = "잡알리오"

    def __init__(self, service_key: str, http: Http | None = None, page_size: int = 100, max_pages: int = 5):
        self.service_key = service_key
        self.http = http or Http()
        self.page_size = page_size
        self.max_pages = max_pages

    def fetch(self) -> list[Posting]:
        postings: list[Posting] = []
        for page_no in range(1, self.max_pages + 1):
            params = {"serviceKey": self.service_key, "pageNo": page_no, "numOfRows": self.page_size,
                      "resultType": "json", "ongoingYn": "Y", "hireTypeLst": HIRE_TYPE_YOUTH_INTERN}
            try:
                text = self.http.get_text(LIST_URL + "?" + urllib.parse.urlencode(params))
            except HttpError as e:
                raise SourceError(str(e)) from None
            except OSError as e:
                reason = getattr(e, "reason", None) or e
                raise SourceError(f"연결 실패 ({e.__class__.__name__}: {reason})") from None
            found, total = parse_page(text)
            postings.extend(found)
            if len(found) < self.page_size or len(postings) >= total:
                break
        return postings
