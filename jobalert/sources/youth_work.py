"""청년일경험 포털 (yw.work24.go.kr)

공식 API 가 없어서 로그인 없이 누구나 보는 '일경험 프로그램 목록' 페이지를 읽는다.
- robots.txt 는 이 목록을 막지 않는다. 약관이 금지하는 건 개인정보 수집·자동 로그인이다.
- 하루 2번, 직무 IT 한 가지만, 몇 페이지만 요청해서 사이트에 부담을 주지 않는다.
- 목록에는 학력 조건이 없다 → education_limited = None (확인 못 함)
"""
import html
import re
import unicodedata
from datetime import date

from ..errors import SourceError
from ..http import Http, HttpError
from ..model import Posting

LIST_URL = "https://yw.work24.go.kr/d/a/selectWkexPrgmList.do"
DUTY_IT = "14"           # 직무 코드: 14 = IT
SORT_RECENT = "C"        # 정렬: C = 최근모집일순

PROGRAM_TYPES = {"I": "인턴형", "P": "프로젝트형", "E": "ESG지원형", "C": "기업탐방형"}

CARD_SPLIT = re.compile(r'<li>\s*<div class="card">')
RE_ID = re.compile(r"fn_searchDetail\('(\w+)',\s*'([A-Z0-9]+)'\)")
RE_TITLE = re.compile(r'<div class="link">\s*<a [^>]*>\s*<strong>(.*?)</strong>', re.S)
RE_SHARE = re.compile(r'data-shtn-url="([^"]+)"')
RE_FIELD = re.compile(r"<li><strong>([^<]+)</strong><span>(.*?)</span></li>", re.S)
RE_PERIOD_END = re.compile(r"~\s*(\d{2})-(\d{2})-(\d{2})")


def _clean(text: str) -> str:
    """태그 제거, &#8203;(보이지 않는 공백) 제거, 전각 괄호（）같은 문자를 보통 문자로"""
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("​", "")
    return " ".join(unicodedata.normalize("NFKC", text).split())


def parse_cards(page: str) -> list[Posting]:
    if 'class="card-list' not in page:
        raise SourceError("목록을 찾지 못함 (사이트 구조가 바뀌었거나 점검 중)")

    postings = []
    for card in CARD_SPLIT.split(page)[1:]:
        fields = {_clean(k): _clean(v) for k, v in RE_FIELD.findall(card)}
        id_match, title_match = RE_ID.search(card), RE_TITLE.search(card)
        if not id_match or not title_match:
            continue
        end = RE_PERIOD_END.search(fields.get("모집기간", ""))
        share = RE_SHARE.search(card)
        postings.append(Posting(
            source="청년일경험",
            source_id=id_match.group(2),
            program_type=PROGRAM_TYPES.get(id_match.group(1), id_match.group(1)),
            company=fields.get("참여기업", ""),
            title=_clean(title_match.group(1)),
            kind="일경험",
            region=fields.get("지역", ""),
            job_field=fields.get("직무", ""),
            deadline=date(2000 + int(end.group(1)), int(end.group(2)), int(end.group(3))) if end else None,
            url=share.group(1).replace(":443", "") if share else "https://yw.work24.go.kr/d/a/selectWkexPrgmList.do",
        ))
    return postings


class YouthWorkSource:
    name = "청년일경험"

    def __init__(self, http: Http | None = None, page_size: int = 48, max_pages: int = 5):
        self.http = http or Http()
        self.page_size = page_size
        self.max_pages = max_pages

    def fetch(self) -> list[Posting]:
        postings: list[Posting] = []
        for page_no in range(1, self.max_pages + 1):
            form = {"currentPageNo": str(page_no), "recordCountPerPage": str(self.page_size),
                    "sortOption": SORT_RECENT, "dtyCd": DUTY_IT}
            try:
                page = self.http.post_form(LIST_URL, form)
            except HttpError as e:
                raise SourceError(str(e)) from None
            except OSError as e:                      # 연결 실패·시간 초과 (원인에는 주소가 들어 있지 않음)
                reason = getattr(e, "reason", None) or e
                raise SourceError(f"연결 실패 ({e.__class__.__name__}: {reason})") from None
            found = parse_cards(page)
            postings.extend(found)
            if len(found) < self.page_size:           # 마지막 페이지
                break
        return postings
