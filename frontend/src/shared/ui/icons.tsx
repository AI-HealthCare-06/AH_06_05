// 아이콘 — 와이어프레임 SVG 그대로 (선 굵기 1.8 · 22 크기)
import Svg, { Circle, G, Path, Rect } from 'react-native-svg';

import { C } from '@/shared/theme';

type IconProps = { color?: string; size?: number };

const line = { fill: 'none', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' } as const;

export function HomeIcon({ color = C.text3, size = 22 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line} stroke={color}>
      <Path d="M3 11 12 3l9 8" />
      <Path d="M5 10v10h5v-6h4v6h5V10" />
    </Svg>
  );
}

export function ChallengeIcon({ color = C.text3, size = 22 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line} stroke={color}>
      <Circle cx="12" cy="12" r="9" />
      <Path d="m9 12 2 2 4-4" />
    </Svg>
  );
}

export function MeIcon({ color = C.text3, size = 22 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line} stroke={color}>
      <Circle cx="12" cy="8" r="4" />
      <Path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
    </Svg>
  );
}

// 뒤로 가기 화살표 (공통 상단 바). 그림 왼쪽이 24칸 중 9칸 뒤에서 시작해서 바깥 여백을 9만큼 당겨 씀
export function BackIcon({ color = C.text, size = 24 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line} strokeWidth={2.2} stroke={color}>
      <Path d="m15 6-6 6 6 6" />
    </Svg>
  );
}

// 닫기 × (챗봇 창 머리: 설계 메모 4-1 "제목 + 달력 + × 닫기")
export function CloseIcon({ color = C.text, size = 24 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line} strokeWidth={2.2} stroke={color}>
      <Path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  );
}

// 문서 (근거와 출처 카드 머리)
// 달력 (챗봇 창 머리, 대화 기록)
export function CalendarIcon({ color = C.text2, size = 24 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line} strokeWidth={2} stroke={color}>
      <Rect x={3} y={5} width={18} height={16} rx={2} />
      <Path d="M3 10h18M8 3v4M16 3v4" />
    </Svg>
  );
}

export function DocIcon({ color = C.text2, size = 18 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line} stroke={color}>
      <Path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <Path d="M14 3v5h5M9 13h6M9 17h6" />
    </Svg>
  );
}

// 챗봇 입력창 받아쓰기 안내 (와이어프레임 CB-01 ⑧)
// 더하기 (첨부)
export function PlusIcon({ color = C.text2, size = 24 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line} strokeWidth={2.2} stroke={color}>
      <Path d="M12 5v14M5 12h14" />
    </Svg>
  );
}

// 소리 (답변 듣기)
export function SpeakerIcon({ color = C.text2, size = 18 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line} stroke={color}>
      <Path d="M4 9v6h4l5 4V5L8 9H4z" />
      <Path d="M16 9a4 4 0 0 1 0 6" />
    </Svg>
  );
}

// 멈춤 (답변 듣기 중)
export function StopIcon({ color = C.text2, size = 18 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line} stroke={color}>
      <Rect x="6" y="6" width="12" height="12" rx="2" />
    </Svg>
  );
}

export function MicIcon({ color = C.text2, size = 20 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line} stroke={color}>
      <Rect x="9" y="3" width="6" height="11" rx="3" />
      <Path d="M5 11a7 7 0 0 0 14 0" />
      <Path d="M12 18v3" />
    </Svg>
  );
}

export function CameraIcon({ color = C.p700, size = 26 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" {...line} stroke={color}>
      <Path d="M3 7h4l2-3h6l2 3h4v12H3V7Z" />
      <Circle cx="12" cy="13" r="4" />
    </Svg>
  );
}

// 챗봇 버튼 — 말풍선 안 캡슐 약
export function ChatbotIcon({ size = 30 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path
        d="M4.5 4.5h15a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2H12l-5 4v-4H4.5a2 2 0 0 1-2-2V6.5a2 2 0 0 1 2-2z"
        fill={C.onPrimary}
      />
      <G transform="rotate(-35 12 10.75)">
        <Rect x="7" y="8.5" width="10" height="4.5" rx="2.25" fill="#93C5FD" />
        <Rect x="12" y="8.5" width="5" height="4.5" rx="2.25" fill={C.p600} />
        <Rect x="11.4" y="8.5" width="1.6" height="4.5" fill={C.p600} />
      </G>
    </Svg>
  );
}
