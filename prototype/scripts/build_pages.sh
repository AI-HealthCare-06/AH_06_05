#!/bin/sh
# gh-pages 배포용 파일 만들기 → prototype/pages/
# 사용: cd prototype && sh scripts/build_pages.sh
# 결과물(pages/)을 팀 저장소 gh-pages 브랜치 최상위에 그대로 덮어써서 올리면 됨 (README "배포" 참고)
set -e
cd "$(dirname "$0")/.."
npx expo export --platform web
rm -rf pages && mkdir -p pages/js
cp dist/_expo/static/js/web/index-*.js pages/js/app.js
cp web/pages-index.html pages/index.html
cp dist/favicon.ico pages/favicon.ico
echo "완료: pages/ (index.html · js/app.js · favicon.ico)"
