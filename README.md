# GitHub 주간 Trending TOP 10

[GitHub 주간 Trending](https://github.com/trending?since=weekly)에 오른 저장소 중 주간 스타 수로 집계한 TOP 10입니다. 페이지의 후보 전체를 주간 스타 수 내림차순으로 정렬하고, 동점이면 대소문자를 구분하지 않는 `소유자/저장소` 이름순으로 정렬합니다.

`reports/YYYY-Www.json`에는 수집 시각, 출처, 순위, 저장소 이름과 URL, 설명, 주간 스타 수를 기록합니다. 파일명은 실제 수집 시각의 한국 시간 ISO 주차를 따릅니다. 같은 주차에 다시 수집하면 검증을 마친 리포트로 파일 하나를 교체합니다. 후보가 10개 미만이거나 후보 파싱 또는 검증에 실패하면 기존 파일을 보존하고 오류로 종료합니다.

## 로컬에서 실행

Python 3.9 이상과 시스템의 IANA 시간대 데이터가 필요합니다. 수집에는 인터넷 연결이 필요하며 테스트는 오프라인에서 실행할 수 있습니다.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/collect.py
python3 scripts/build.py
python3 -m http.server 8000 --directory dist
```

브라우저에서 `http://localhost:8000/`를 열면 최신 순위, 지난 주차별 페이지, 공유 문구 복사 버튼을 볼 수 있습니다. RSS는 `dist/feed.xml`에 생성되고 항목의 GUID는 같은 주차의 리포트를 갱신해도 유지됩니다. 별도 도메인이나 포트에서 빌드할 때는 `scripts/build.py --base-url`로 RSS 및 공유 링크에 사용할 사이트 주소를 지정합니다.

## GitHub Pages 설정

1. 워크플로 파일을 저장소의 기본 브랜치에 추가합니다.
2. **Settings → Pages → Build and deployment → Source**에서 **GitHub Actions**를 선택합니다.
3. **Actions → Weekly GitHub Trending → Run workflow**에서 기본 브랜치를 선택하여 수동 실행할 수 있습니다.

워크플로는 매주 수요일 오전 06:40(Asia/Seoul)에 예약 실행됩니다. 수집과 검증에 성공하면 주차별 JSON을 기본 브랜치에 커밋합니다. 이어서 해당 커밋의 리포트로 사이트를 빌드하고, `dist/`를 업로드한 뒤 같은 실행에서 Pages에 배포합니다. 기본 브랜치 보호 규칙이 워크플로의 커밋을 차단하면 커밋 단계에서 종료됩니다. [GitHub Pages 사용자 지정 워크플로 문서](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

## 주간 카드뉴스

**Settings → Secrets and variables → Actions → Secrets**에서 `GEMINI_API_KEY`를 Repository Secret으로 등록합니다. 모델을 지정하려면 같은 화면의 **Variables**에 `GEMINI_MODEL`을 추가합니다. 변수가 비어 있으면 `gemini-3.5-flash-lite`를 사용합니다.

워크플로는 TOP 10 리포트와 일치하는 기존 카드뉴스가 있으면 재사용합니다. 새로 생성할 때는 공개 README와 저장소 설명으로 한국어 문구를 만들고, Chrome으로 1080×1350 PNG 11장을 렌더링합니다. 파일은 `card-news/YYYY-Www/`에 보관합니다. 완성된 카드 세트는 Pages에 포함되고 해당 리포트에 **카드뉴스 보기** 링크가 표시됩니다. 키가 비어 있거나 카드 생성에 실패한 주에도 순위 페이지는 배포됩니다.

로컬에서 새 카드를 만들려면 환경 변수로 키를 전달한 상태에서 `python3 scripts/generate_cards.py reports/YYYY-Www.json`을 실행합니다. PNG 렌더링에는 Node.js, Chrome 및 한국어 폰트가 필요합니다. Chrome이 기본 경로에 없으면 `CHROME_BIN`으로 실행 파일 경로를 지정할 수 있습니다.

## 스킬 순위

사이트의 **Skill Leaderboard**와 **skills.sh** 탭은 같은 수요일 워크플로에서 갱신합니다. Skill Leaderboard는 공개 카탈로그의 저장소를 7일 스타 증가량으로 정렬합니다. skills.sh는 수집 당시 Trending에 표시된 **최근 24시간 설치 수**를 주차별로 기록합니다. 각 탭에서 해당 출처의 TOP 10, 지난 리포트, 카드뉴스를 볼 수 있습니다. [Skill Leaderboard 카탈로그](https://www.skillleaderboard.com/api/catalog) · [skills.sh Trending](https://www.skills.sh/trending)

스킬 리포트와 카드뉴스는 각각 `reports/<출처>/YYYY-Www.json`과 `card-news/<출처>/YYYY-Www/`에 저장합니다. 다시 순위권에 들어온 항목은 같은 출처의 안정적인 식별자로 찾고, 기존 문구와 PNG를 재사용합니다. 주차, 순위, 지표는 새 표지와 리포트에 표시됩니다. 한 출처의 수집이나 카드 생성에 실패하면 기존 파일을 보존하고 나머지 출처를 계속 처리합니다.

로컬 수집은 `python3 scripts/collect_skills.py skill-leaderboard`와 `python3 scripts/collect_skills.py skills-sh`를 사용합니다. 카드 생성 명령에는 해당 출처의 리포트 경로를 전달합니다.

## Hugging Face 모델 순위

**Hugging Face 모델** 탭은 매주 수집한 모델 목록의 `trendingScore` 상위 10개를 표시합니다. 리포트는 `reports/huggingface-models/YYYY-Www.json`에 저장합니다. 로컬에서 갱신하려면 `python3 scripts/collect_huggingface.py`를 실행한 뒤 사이트를 빌드합니다. [Hugging Face 모델 트렌딩](https://huggingface.co/models?sort=trending)

## Teams 배포 알림

Teams Workflows의 **Send webhook alerts to a channel** 템플릿에서 발급한 URL을 저장소의 Actions Secret `TEAMS_WEBHOOK_URL`에 등록합니다. 웹훅에서 **Anyone** 인증 옵션을 사용하는 경우 URL만으로 요청을 보낼 수 있으므로 URL을 코드나 로그에 남기지 않습니다. [Teams 웹훅 설정](https://support.microsoft.com/en-gb/workflows/send-messages-in-teams-using-incoming-webhooks)

Pages 배포 성공 후 출처별로 Teams Adaptive Card를 게시합니다. 각 게시물에는 출처가 표시된 표지와 순위별 이미지 10장이 들어갑니다. 넓은 화면에서는 한 줄에 3장, 좁은 화면에서는 2장을 표시합니다. 데스크톱에서는 이미지에 마우스를 올려 확대 아이콘을 누르고, 모바일에서는 이미지를 눌러 Teams 안에서 확대할 수 있습니다. 카드 하단의 **자세히 보기**는 해당 출처의 주간 리포트를 엽니다. 웹훅 요청과 채널 게시 결과는 각각 Actions의 `notify-teams` 작업과 Teams 워크플로 실행 기록에서 확인할 수 있습니다.
