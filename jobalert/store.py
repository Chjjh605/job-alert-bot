"""보낸 공고 기록

저장소가 공개라서 제목·회사명을 그대로 남기지 않는다(희망 직무·지역 노출 방지).
같은 공고 판별 키를 해시로 바꿔서 저장한다. (docs/adr/0002 참고)
"""
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


def hashed(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


@dataclass
class SentRecord:
    deadline: date | None     # 알림을 보낼 때의 마감일 (None = 상시채용)
    sent_on: date


@dataclass
class State:
    sent: dict[str, SentRecord] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "State":
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        sent = {
            k: SentRecord(
                deadline=date.fromisoformat(v["deadline"]) if v.get("deadline") else None,
                sent_on=date.fromisoformat(v["sent_on"]),
            )
            for k, v in raw.get("sent", {}).items()
        }
        return cls(sent=sent)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = {
            "sent": {
                k: {"deadline": r.deadline.isoformat() if r.deadline else None,
                    "sent_on": r.sent_on.isoformat()}
                for k, r in sorted(self.sent.items())
            },
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)     # 쓰다가 멈춰도 기존 기록이 깨지지 않게

    def already_sent(self, key: str, today: date) -> bool:
        """이미 알림을 보냈고 그 공고가 아직 마감 전이면 True.
        마감이 지난 뒤 같은 공고가 다시 보이면 재공고이므로 False."""
        record = self.sent.get(hashed(key))
        if record is None:
            return False
        return record.deadline is None or record.deadline >= today

    def mark_sent(self, key: str, deadline: date | None, today: date) -> None:
        self.sent[hashed(key)] = SentRecord(deadline=deadline, sent_on=today)
