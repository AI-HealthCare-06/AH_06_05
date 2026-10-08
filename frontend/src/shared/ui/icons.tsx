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
