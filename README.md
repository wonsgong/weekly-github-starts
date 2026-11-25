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
