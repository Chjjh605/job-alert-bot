"""공고와 관심 조건 (용어는 CONTEXT.md 참고)"""
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Posting:
    """공고 하나. 출처마다 모양이 다른 원본 데이터를 이 형태로 맞춘다."""
    source: str                    # 출처 이름 (예: 청년일경험)
    source_id: str                 # 출처 안에서의 고유 번호
    company: str
    title: str
    kind: str                      # 공고 종류: 인턴 / 일경험 / 신입
    region: str
    job_field: str                 # 출처가 주는 직무 분류 (없으면 빈 문자열)
    deadline: date | None          # None 이면 상시채용
    url: str
    education_limited: bool | None = None   # 학력 제한 여부, None 이면 출처가 알려 주지 않음
    program_type: str = ""                  # 일경험 유형 (인턴형/프로젝트형/ESG지원형/기업탐방형), 일경험이 아니면 빈 문자열


@dataclass(frozen=True)
class InterestConditions:
    """관심 조건"""
    job_keywords: list[str]
    kinds: list[str]
    regions: list[str]
    exclude_keywords: list[str] = field(default_factory=list)
    program_types: list[str] = field(default_factory=list)   # 받을 일경험 유형 (일경험 공고에만 적용)
