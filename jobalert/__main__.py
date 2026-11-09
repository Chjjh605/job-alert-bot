"""실행 방법

  python -m jobalert            실제 실행: 새 공고를 Discord 로 보내고 기록을 남김
  python -m jobalert --dry-run  테스트 실행: 보낼 공고를 화면에만 출력 (기록은 바뀌지 않음)
  pythonw -m jobalert --log-file state/run.log   작업 스케줄러용: 창 없이 실행, 결과는 파일에

비밀 값은 환경변수 또는 .env 파일로 넣는다 (.env 는 GitHub 에 올라가지 않음)
  DISCORD_WEBHOOK_URL   Discord 채널 웹훅 주소
  JOBALIO_SERVICE_KEY   공공데이터포털 인증키 (잡알리오, 없으면 잡알리오는 건너뜀)
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .discord import build_embed
from .discord import DiscordNotifier
from .model import InterestConditions
from .run import run_once
from .sources.jobalio import JobAlioSource
from .sources.youth_work import YouthWorkSource

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))   # GitHub Actions 서버는 UTC 라서 한국 시간을 직접 지정


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class ConsolePrinter:
    """--dry-run 용: Discord 대신 화면에 출력"""
    def send_posting(self, postings, now):
        card = build_embed(postings, now)
        fields = {f["name"]: f["value"] for f in card["fields"]}
        print(f"  (보낼 예정) {card['title']} | {fields['회사']} | {fields['지역']} | 마감 {fields['마감']}")

    def send_text(self, text):
        print(f"  (보낼 글) {text}")

    def send_deadline_reminder(self, groups, now):
        print(f"  (마감 임박 알림) 내일 마감 {len(groups)}건: " + ", ".join(g[0].title for g in groups))


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # 윈도우 콘솔 한글 깨짐 방지
    except Exception:
        pass
    parser = argparse.ArgumentParser(prog="jobalert")
    parser.add_argument("--dry-run", action="store_true", help="Discord 로 보내지 않고 화면에만 출력")
    parser.add_argument("--state", default=str(ROOT / "state" / "state.json"))
    parser.add_argument("--log-file", help="출력을 화면 대신 이 파일 끝에 덧붙임 (작업 스케줄러용)")
    args = parser.parse_args(argv)

    if args.log_file:     # 작업 스케줄러는 창 없이(pythonw) 실행하므로 결과를 파일로 남긴다
        Path(args.log_file).parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(args.log_file, "a", encoding="utf-8", buffering=1)

    load_dotenv(ROOT / ".env")
    conditions = InterestConditions(**json.loads((ROOT / "config.json").read_text(encoding="utf-8")))
    # 출처별로 요청할 때 범위를 좁힌다: 청년일경험은 IT 직무, 잡알리오는 체험형 청년인턴(직무 무관)
    sources = [YouthWorkSource()]
    jobalio_key = os.environ.get("JOBALIO_SERVICE_KEY", "").strip()
    if jobalio_key:
        sources.append(JobAlioSource(jobalio_key))
    else:
        print("JOBALIO_SERVICE_KEY 가 없어 잡알리오는 건너뜁니다.")
    state_path = Path(args.state)

    if args.dry_run:
        notifier = ConsolePrinter()
        tmp = Path(tempfile.mkdtemp()) / "state.json"     # 실제 기록을 건드리지 않도록 복사본 사용
        if state_path.exists():
            shutil.copy(state_path, tmp)
        state_path = tmp
    else:
        webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        if not webhook:
            print("DISCORD_WEBHOOK_URL 이 없습니다. .env 파일이나 GitHub Secrets 에 넣어 주세요.")
            return 2
        notifier = DiscordNotifier(webhook)

    now = datetime.now(KST)
    report = run_once(sources, notifier, state_path, conditions, now)

    fetched = ", ".join(f"{name} {n}건" for name, n in report.fetched.items()) or "없음"
    print(f"[{now:%Y-%m-%d %H:%M}] 가져온 공고: {fetched} / 새로 알린 공고: {report.sent}건")
    on_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    for error in report.errors:
        # GitHub Actions 에서는 ::error:: 로 찍으면 실행 화면 맨 위 'Annotations' 에 원인이 바로 보인다
        print(f"::error::{error}" if on_actions else f"  오류: {error}")
    if on_actions and os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"### 실행 결과 ({now:%Y-%m-%d %H:%M} KST)\n\n"
                    f"- 가져온 공고: {fetched}\n- 새로 알린 공고: {report.sent}건\n"
                    + "".join(f"- ⚠️ {e}\n" for e in report.errors))
    return 0 if report.ok else 1     # 오류가 있으면 GitHub Actions 가 실패로 표시하고 메일을 보냄


if __name__ == "__main__":
    sys.exit(main())
