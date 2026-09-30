// Figma 00 톤앤매너 가이드 (5팀 Tokens) 값
export const C = {
  p700: '#1D4ED8',
  p600: '#2563EB',
  p500: '#3B82F6',
  p100: '#DBEAFE',
  p50: '#EFF6FF',
  text: '#0F172A',
  text2: '#475569',
  text3: '#94A3B8',
  onPrimary: '#FFFFFF',
  bg: '#F4F7FB',
  card: '#FFFFFF',
  muted: '#F1F5F9',
  border: '#E2E8F0',
  borderStrong: '#CBD5E1',
  danger: '#DC2626',
  dangerBg: '#FEF2F2',
  warning: '#B45309',
  warningBg: '#FFFBEB',
  success: '#047857',
  successBg: '#ECFDF5',
  info: '#1D4ED8',
  infoBg: '#EFF6FF',
  annoBg: '#FFF9E6',
  annoBorder: '#F2D98C',
  annoText: '#8A5A00',
};

export const R = { card: 16, control: 12, chip: 999 };
export const S = { side: 20, gap: 12, section: 24 };

// 글자 크기: 본문 16 이상 (NFR-022)
export const T = {
  title: { fontSize: 24, fontWeight: '700' as const, color: C.text },
  heading: { fontSize: 20, fontWeight: '700' as const, color: C.text },
  subhead: { fontSize: 17, fontWeight: '700' as const, color: C.text },
  body: { fontSize: 16, color: C.text, lineHeight: 24 },
  bodyM: { fontSize: 16, fontWeight: '600' as const, color: C.text, lineHeight: 24 },
  label: { fontSize: 15, fontWeight: '600' as const, color: C.text },
  caption: { fontSize: 14, color: C.text2, lineHeight: 20 },
  small: { fontSize: 13, fontWeight: '600' as const, color: C.text2 },
};
