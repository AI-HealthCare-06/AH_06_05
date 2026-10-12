---
version: alpha
name: AH_06_05 복약 안내 앱
description: 다약제를 먹는 고령 만성질환자, 보호자를 위한 복약 안내 앱(Expo)의 화면 규칙. 값은 frontend/src/shared/theme/index.ts와 같음
colors:
  primary: "#2563EB"
  primary-strong: "#1D4ED8"
  primary-soft: "#3B82F6"
  primary-tint: "#DBEAFE"
  primary-wash: "#EFF6FF"
  on-primary: "#FFFFFF"
  text: "#0F172A"
  text-secondary: "#475569"
  text-disabled: "#94A3B8"
  background: "#F4F7FB"
  surface: "#FFFFFF"
  surface-muted: "#F1F5F9"
  border: "#E2E8F0"
  border-strong: "#CBD5E1"
  danger: "#DC2626"
  danger-bg: "#FEF2F2"
  warning: "#B45309"
  warning-bg: "#FFFBEB"
  warning-border: "#F5C77E"
  success: "#047857"
  success-bg: "#ECFDF5"
  success-border: "#A7E3C8"
  info: "#1D4ED8"
  info-bg: "#EFF6FF"
typography:
  title:
    fontFamily: system-ui
    fontSize: 24px
    fontWeight: 700
  heading:
    fontFamily: system-ui
    fontSize: 20px
    fontWeight: 700
  subhead:
    fontFamily: system-ui
    fontSize: 17px
    fontWeight: 700
  body:
    fontFamily: system-ui
    fontSize: 16px
    fontWeight: 400
    lineHeight: 24px
  body-strong:
    fontFamily: system-ui
    fontSize: 16px
    fontWeight: 600
    lineHeight: 24px
  button:
    fontFamily: system-ui
    fontSize: 17px
    fontWeight: 700
  label:
    fontFamily: system-ui
    fontSize: 15px
    fontWeight: 600
  caption:
    fontFamily: system-ui
    fontSize: 14px
    fontWeight: 400
    lineHeight: 20px
  small:
    fontFamily: system-ui
    fontSize: 13px
    fontWeight: 600
rounded:
  chip: 999px
  card: 16px
  control: 12px
spacing:
  gap: 12px
  card-padding: 16px
  side: 20px
  section: 24px
  touch-min: 48px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    height: 56px
  button-secondary:
    backgroundColor: "{colors.primary-wash}"
    textColor: "{colors.primary-strong}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    height: 56px
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    height: 56px
  button-disabled:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.text-disabled}"
    rounded: "{rounded.control}"
    height: 56px
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.card}"
    padding: "{spacing.card-padding}"
  card-danger:
    backgroundColor: "{colors.danger-bg}"
    textColor: "{colors.text}"
    rounded: "{rounded.card}"
    padding: "{spacing.card-padding}"
  card-caution:
    backgroundColor: "{colors.warning-bg}"
    textColor: "{colors.text}"
    rounded: "{rounded.card}"
    padding: "{spacing.card-padding}"
  chip-danger:
    backgroundColor: "{colors.danger-bg}"
    textColor: "{colors.danger}"
    typography: "{typography.small}"
    rounded: "{rounded.chip}"
  chip-caution:
    backgroundColor: "{colors.warning-bg}"
    textColor: "{colors.warning}"
    typography: "{typography.small}"
    rounded: "{rounded.chip}"
  chip-success:
    backgroundColor: "{colors.success-bg}"
    textColor: "{colors.success}"
    typography: "{typography.small}"
    rounded: "{rounded.chip}"
  chip-info:
    backgroundColor: "{colors.info-bg}"
    textColor: "{colors.info}"
    typography: "{typography.small}"
    rounded: "{rounded.chip}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
  top-tab:
    textColor: "{colors.primary-strong}"
    height: 48px
  bottom-nav:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    height: 64px
  chatbot-launcher:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.chip}"
    size: 56px
---

> 화면 규칙. 구글 design.md 형식이라 위 YAML은 기계가 읽는 값, 아래는 쓰는 방법. 저장소 루트에 둠. 바꿀 때는 PR로 고치고 맨 아래 변경 이력을 남김
> 값 출처: `frontend/src/shared/theme/index.ts` (Figma 00 톤앤매너 가이드 5팀 Tokens), 공통 부품 `frontend/src/shared/ui`

## Overview

**누구를 위한 화면인가**: 여러 약을 먹는 고령 만성질환자와 그 보호자. 휴대폰을 한 손으로 쓰고, 작은 글씨와 작은 버튼이 어렵다.

**분위기**: 병원처럼 차갑지 않고 깔끔한 "모던 블루". 정보는 크게, 장식은 적게. AI가 만든 티(과한 강조, 이모지, 마크다운 기호)가 나지 않게 담백하게.

**세 가지 원칙**
1. **크게**: 본문 16 이상, 누르는 곳 48 이상, 주요 버튼 56 (근거는 Typography, Layout)
2. **한 화면에 한 가지 행동**: 화면마다 가장 중요한 버튼 하나를 크게 (처음 홈은 "처방전 찍기")
3. **색만으로 말하지 않기**: 위험, 주의, 안전은 색과 함께 글자 라벨로 (NFR-024)

**기준으로 삼는 표준**: W3C 웹 접근성 지침 WCAG 2.2 AA, 국내 모바일 앱 접근성 지침 2.0 (WCAG와 같은 4원칙, TTAK.KO-10.0634/R1), iOS, Android 공식 디자인 지침

## Colors

**대비 규칙** (WCAG 2.2): `npx @google/design.md lint`가 자동 검사
| 대상 | 최소 대비 | 근거 |
|---|---|---|
| 일반 글자 | **4.5 : 1** | 1.4.3 (AA) |
| 큰 글자 (18pt 이상, 굵게 14pt 이상) | 3 : 1 | 1.4.3 |
| 아이콘, 입력 칸 테두리, 버튼 모양 | 3 : 1 | 1.4.11 (AA) |
| 누를 수 없는(비활성) 요소 | 기준 없음 | 1.4.3, 1.4.11 예외 |

- **Primary (#2563EB)**: 주요 버튼, 지금 탭, 챗봇 버튼. 한 화면에서 가장 중요한 행동에만 (흰 글자 대비 5.17 : 1)
- **Primary strong (#1D4ED8)**: 보조 버튼 글자, 링크, 상단 탭 글자
- **Primary wash (#EFF6FF)**: 보조 버튼 배경, 안내 카드 배경
- **Text (#0F172A) / Text secondary (#475569, 흰 배경 7.58 : 1)**: 본문 / 설명, 캡션
- **Text disabled (#94A3B8, 흰 배경 2.56 : 1)**: 누를 수 없는 버튼 글자 **전용**: 비활성 요소는 대비 기준의 예외라 허용. 읽어야 하는 글자에는 쓰지 않음
- **Background (#F4F7FB) / Surface (#FFFFFF)**: 화면 바탕 / 카드, 상단바, 하단 내비
- **상태 색**: 늘 글자 라벨과 함께
  - Danger (#DC2626, 배경 #FEF2F2): 같이 먹으면 안 됨, 긴급 안내, 삭제
  - Warning (#B45309, 배경 #FFFBEB): 주의, 확인 필요
  - Success (#047857, 배경 #ECFDF5): 확인된 위험 없음, 완료
  - Info (#1D4ED8, 배경 #EFF6FF): 안내, 참고

## Typography

| 기준 | 값 | 우리 |
|---|---|---|
| Apple 최소 글자 | 11pt | 가장 작은 글자 13 |
| 고령자 글자 크기 연구 (휴대폰, 57~70세) | 10.5~14.5pt가 선호 범위: 너무 커지면 오히려 읽기 떨어지는 지점이 있음 | 본문 16, 제목 24 |
| 요구사항 | 본문 16 이상 (NFR-022) | ✅ |

- 글꼴은 기기 기본 글꼴 (따로 넣지 않음: 앱 크기, 로딩 줄이기)
- 13, 14는 칩, 캡션, 내비 글자처럼 짧은 보조 글에만
- 제목 24 → 묶음 제목 17 → 본문 16 순서로 위계
- 버튼 글자는 17 굵게: 고령 사용자가 버튼을 글자로 찾음
- 한 문장은 짧게, 존댓말 "~해요"체. 의학 용어는 쉬운 말로 바꾸고 필요하면 괄호로 원래 말
- 휴대폰 글자 크기 설정을 키워도 화면이 깨지지 않게 (줄바꿈 허용, 높이를 글자 크기로 고정하지 않음)

## Layout

**누르는 곳 크기**: 세 기준 중 가장 큰 것을 따름
| 기준 | 최소 |
|---|---|
| WCAG 2.2 2.5.8 (AA) | 24 × 24 |
| Apple | 44 × 44pt |
| Android | 48 × 48dp, "클수록 좋음" |
| **우리** | **48 이상, 주요 버튼 56** (고령 사용자) |

- 좌우 여백 20, 카드 사이 12, 묶음 사이 24
- **아래 고정 버튼**이 있는 화면은 본문 아래 여백을 버튼 높이 + 기기 안전 영역만큼
- **내비**: 홈만 상단 탭(제목 줄 56 + 탭 줄 48), 나머지 화면은 하단 내비 3개(64 + 안전 영역)
- **챗봇 버튼**: 오른쪽 16, 맨 아래 요소 위 16. 하단 내비가 있으면 그 위로, 아래 고정 버튼이 있으면 숨기거나 그 위로 (9/29 멘토링)
- 모든 화면은 기기 안전 영역(노치, 홈 막대, 제스처 바)을 피함

## Elevation & Depth

- 기본은 그림자 없이 테두리(#E2E8F0)로 구분
- 그림자는 **떠 있는 것**에만: 챗봇 플로팅 버튼(파란 그림자), 아래에서 올라오는 시트, 확인 창
- 확인 창, 시트 뒤는 어둡게(검정 45%) 덮어 지금 할 일에 집중

## Shapes

- 카드 16, 버튼, 입력 칸 12, 칩, 챗봇 버튼은 완전한 원
- 아이콘은 선 굵기 1.8, 크기 22 (내비), 끝을 둥글게

## Components

| 부품 | 쓰는 곳 | 규칙 |
|---|---|---|
| **버튼** (primary, secondary, danger, ghost) | 화면의 행동 | 높이 56, 한 화면에 primary는 하나. 누를 수 없으면 회색 + 스크린 리더에 "사용 불가"(`accessibilityState.disabled`) |
| **카드** (기본, danger, caution, info, success) | 정보 묶음, 경고 | 상태 카드는 칩(라벨)과 함께 |
| **칩** | 상태 라벨 ("주의", "확인 필요", "완료") | 색만 쓰지 않고 반드시 글자 |
| **입력 칸** | 로그인, 가입, 검색 | 라벨을 칸 위에, 오류는 칸 아래 "※ …" 빨간 글자. 칸 테두리는 배경과 3 : 1 이상 |
| **체크, 라디오** | 동의, 선택 | 줄 높이 48 이상, 글자를 눌러도 선택, 선택 상태를 스크린 리더에 (`checked`) |
| **확인 창** | 삭제, 탈퇴, 되돌릴 수 없는 일 | 위험한 버튼은 danger, 취소는 secondary |
| **상단 탭 / 하단 내비** | 홈, 실천, 내정보 | 지금 탭은 파란색 + (상단은 밑줄 3), 스크린 리더에 "선택됨"(`selected`) |
| **챗봇 버튼** | 어느 화면에서든 | 아이콘만(말풍선 안 캡슐 약) 56 원형, 새 답변은 빨간 점, 스크린 리더 이름 "AI 챗봇 열기": 아이콘만 있는 버튼은 반드시 이름을 붙이고, 이름에 "버튼"을 넣지 않음(역할로 알려 줌) |

**스크린 리더 (React Native)**
- 누르는 것에는 `accessibilityRole`(button, checkbox, radio, tab, header)과 `accessibilityLabel`
- 상태는 `accessibilityState`(disabled, selected, checked)로
- 라벨만으로 결과가 분명하지 않으면 `accessibilityHint`

- 새 화면은 `frontend/src/shared/ui`의 부품을 먼저 쓰고, 없을 때만 새로 만듦
- 화면 문구는 `frontend/src/shared/copy`에 모아 둠

## Do's and Don'ts

**Do**
- 화면마다 가장 중요한 행동 하나를 primary 버튼으로 크게
- 상태는 색 + 글자 라벨 함께
- 아이콘만 있는 버튼에는 스크린 리더 이름을 붙임
- 의학적 판단이 아니라는 안내("의학적 진단 · 처방이 아닌 참고용 안내예요", 화면 문구 그대로)를 결과, 챗봇 화면에 둠
- 값은 `theme`에서 가져다 씀 (화면 코드에 색, 크기를 직접 쓰지 않음)
- 바꾼 뒤 `npx @google/design.md lint`로 대비를 확인

**Don't**
- 본문을 16보다 작게, 누르는 곳을 48보다 작게
- Text disabled(#94A3B8)를 읽어야 하는 글자에 쓰기: 대비 2.56 : 1
- AI 답변, 안내문에 `**` 같은 마크다운 기호, 이모지 남기기 (10/6 멘토링)
- 같은 문구를 화면마다 반복 (10/6 멘토링: 히어로 문구 반복은 단조로움)
- 이름을 부르는 인사말("○○님, 반가워요") 넣기: AI 티가 남 (10/7 회의)
- 챗봇 버튼이 아래 고정 버튼, 내비를 가리게 두기

---

### 검사 결과 (10/7, `npx @google/design.md lint`)
- 오류 0, 경고 8
- **chip-danger 대비 4.41 : 1**: 일반 글자 기준 4.5 : 1에 조금 못 미침 → 고칠 거리
- button-disabled 2.34 : 1: 비활성 요소는 예외
- 나머지 6개는 "정의했지만 부품에서 안 쓰는 값"(테두리 색 등): 이 형식의 부품 속성에 테두리가 없어서 생김, 문제 아님

### 아직 정하지 않은 것
- [ ] **위험 칩 글자색**: 4.41 : 1 → 진한 빨강 #B91C1C (5.91 : 1)로 바꿀지
- [ ] **하단 내비 꺼진 탭 색**: 지금 #94A3B8 (2.56 : 1). 꺼진 탭도 누를 수 있어 비활성 예외가 아님 → #475569 (7.58 : 1)로 바꿀지
- [ ] **입력 칸 테두리**: 지금 #CBD5E1은 흰 배경 대비 1.48 : 1. 칸 모양을 알아보는 테두리는 3 : 1 이상이어야 함 → #64748B (4.76 : 1)처럼 진하게 할지 (lint는 테두리 속성이 없어 못 잡아 직접 계산함)
- [ ] 처음 홈 행동 버튼(CTA)과 히어로 문구를 어떻게 다듬을지 (10/6 멘토링)
- [ ] 글꼴: 기기 기본 / 한글 글꼴(Pretendard 등)

### 검사 도구
```bash
npx @google/design.md lint DESIGN.md      # 구조, 참조, 대비(WCAG AA) 검사
npx @google/design.md diff old.md new.md  # 바뀐 값 비교
```

## 변경 이력

| 날짜 | 내용 | 작성 |
|---|---|---|
| 2026-10-12 | 첫 버전 | 이수인 |
