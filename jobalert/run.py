"""한 번의 실행: 출처에서 공고 수집 → 관심 조건 확인 → 같은 공고 묶기 → 알림 → 마감 임박 알림 → 기록"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from .errors import SendError, SourceError
from .model import InterestConditions, Posting
from .store import State


@dataclass
class RunReport:
    fetched: dict[str, int] = field(default_factory=dict)   # 출처별 가져온 공고 수
    sent: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def matches(posting: Posting, conditions: InterestConditions, today: date) -> bool:
    """관심 조건에 맞으면 True. 확인할 수 없는 값(학력 정보 없음, 상시채용)은 놓치지 않도록 통과시킨다."""
    text = f"{posting.title} {posting.job_field}"
    if conditions.job_keywords and not any(word in text for word in conditions.job_keywords):
        return False      # 비워 두면 직무로 거르지 않음 (출처에 요청할 때 이미 범위를 좁힌 경우)
    if any(word in posting.title for word in conditions.exclude_keywords):
        return False
    if posting.kind not in conditions.kinds:
        return False
    if posting.program_type and posting.program_type not in conditions.program_types:
        return False
    if not any(place in posting.region for place in conditions.regions):   # 지역무관도 목록에 있어야 통과
        return False
    if posting.education_limited:
        return False
    if posting.deadline is not None and posting.deadline < today:
        return False
    return True


def same_posting_key(posting: Posting) -> str:
    """같은 공고 판별 기준: 회사명 + 제목 (띄어쓰기 차이는 무시)"""
    return " ".join(f"{posting.company} {posting.title}".split())


def run_once(sources, notifier, state_path: Path, conditions: InterestConditions,
             now: datetime) -> RunReport:
    today = now.date()
    state = State.load(state_path)
    report = RunReport()

    # ① 수집: 출처 하나가 실패해도 나머지는 계속
    groups: dict[str, list[Posting]] = {}       # 같은 공고끼리 묶음 (출처 순서 유지)
    for source in sources:
        try:
            postings = source.fetch()
        except SourceError as e:
            report.errors.append(f"{source.name} 수집 실패: {e}")
            continue
        report.fetched[source.name] = len(postings)
        for posting in postings:
            if matches(posting, conditions, today):
                groups.setdefault(same_posting_key(posting), []).append(posting)

    # ② 알림: 보내는 데 성공한 것만 기록 → 실패한 건 다음 실행 때 다시 보냄
    fresh: set[str] = set()                     # 이번 실행에서 처음 알린 공고
    for key, group in groups.items():
        if state.already_sent(key, today):
            continue
        try:
            notifier.send_posting(group, now)
        except SendError as e:
            report.errors.append(f"알림 전송 실패: {e}")
            continue
        state.mark_sent(key, group[0].deadline, today)
        fresh.add(key)
        report.sent += 1

    # ③ 마감 임박 알림: 그날 첫 실행 때 한 번. 수집이 실패했으면 빠진 공고가 있을 수 있으니 다음 실행으로 미룸
    collect_failed = any("수집 실패" in e for e in report.errors)
    if state.last_reminder != today and not collect_failed:
        tomorrow = today + timedelta(days=1)
        due = [group for key, group in groups.items()
               if key not in fresh and state.already_sent(key, today) and group[0].deadline == tomorrow]
        try:
            if due:
                notifier.send_deadline_reminder(due, now)
            state.last_reminder = today
        except SendError as e:
            report.errors.append(f"마감 임박 알림 전송 실패: {e}")

    state.save(state_path)

    # ④ 수집 실패 알림 (Discord 자체가 고장이면 이것도 못 가지만, state/run.log 에는 남음)
    failures = [e for e in report.errors if "수집 실패" in e]
    if failures:
        try:
            notifier.send_text("⚠️ 수집 실패 알림\n" + "\n".join(f"- {e}" for e in failures)
                               + "\n다음 실행 때 자동으로 다시 시도합니다.")
        except SendError as e:
            report.errors.append(f"수집 실패 알림 전송 실패: {e}")
    return report
