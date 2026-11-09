---
status: superseded by ADR-0003
---

# GitHub Actions로 실행하고, 보낸 공고 기록은 bot-state 브랜치에 커밋한다

봇은 GitHub Actions에서 하루 두 번(09시·18시 KST) 돈다. 실행이 끝날 때마다 "이미 알림을 보낸 공고" 기록을 코드와 분리된 `bot-state` 브랜치에 커밋한다. 서버를 따로 두지 않아도 되고 무료이며, 실행 기록이 GitHub 화면에 남는다.

> 2026-11-09 실제로 돌려 보니 청년일경험 포털이 GitHub Actions 서버(해외 IP)의 접속을 받지 않았다. [ADR 0003](0003-내-PC-작업-스케줄러로-실행.md)으로 대체.

## Considered Options

- 내 PC 작업 스케줄러: PC가 꺼져 있으면 돌지 않는다. GitHub Actions가 해외 IP 때문에 막힐 경우의 대안으로 남긴다.
- 기록을 Actions 캐시에 두기: 7일 동안 쓰지 않으면 지워지고, 그러면 예전 공고 알림이 한꺼번에 다시 온다.
- 기록을 main 브랜치에 커밋하기: 1년에 700개 넘는 자동 커밋이 코드 기록에 섞이고, 직접 push할 때 충돌이 난다.
