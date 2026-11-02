// 답변 읽어주기 (설계 메모 4-11). 한 번에 하나만 재생하고, 창을 닫거나 달력으로 가면 멈춤. 속도 0.9배, 한국어
import * as Speech from 'expo-speech';
import { useSyncExternalStore } from 'react';

const RATE = 0.9; // 고령 사용자 (설계 메모 4-11)
const LANGUAGE = 'ko-KR';

let current: string | null = null; // 재생 중인 말풍선 번호
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((l) => l());

function set(id: string | null) {
  current = id;
  notify();
}

export function speak(id: string, text: string) {
  Speech.stop();
  set(id);
  const done = () => {
    if (current === id) set(null);
  };
  Speech.speak(text, { language: LANGUAGE, rate: RATE, onDone: done, onStopped: done, onError: done });
}

export function stopSpeaking() {
  Speech.stop();
  set(null);
}

// 재생 중인 말풍선 번호. 없으면 null
export function useSpeaking(): string | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => current,
    () => current,
  );
}

// 기기에 한국어 음성이 있는지. 목록을 아직 못 받았으면(웹은 처음에 빈 목록) 있다고 봄
let korean: boolean | null = null;
export async function hasKoreanVoice(): Promise<boolean> {
  if (korean !== null) return korean;
  try {
    const voices = await Speech.getAvailableVoicesAsync();
    korean = voices.length === 0 || voices.some((v) => v.language.toLowerCase().startsWith('ko'));
  } catch {
    korean = true;
  }
  return korean;
}
