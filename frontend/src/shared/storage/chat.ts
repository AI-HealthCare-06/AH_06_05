// 기기에 남기는 챗봇 값 (설계 메모 3-3, 4-7, 4-10 항목)
// - 실패한 질문: 창을 닫았다 열거나 앱을 다시 켜도 E6 카드와 함께 보이게. 다시 보내기에 성공하면 지움
//   오늘(한국 시간) 것만 둠: 1단계는 하루 한 대화라 날이 바뀌면 그 대화를 다시 열 길이 없음. 로그인이 끝나면 지움 (10/26 수인 결정)
//   질문 글은 건강 정보라 휴대폰은 출입증과 같은 expo-secure-store. 웹은 출입증처럼 개발 확인용 localStorage
//   secure-store 값 하나가 커지지 않게 질문마다 칸을 나누고, 칸 이름 목록만 따로 둠
// - 받아쓰기 안내를 본 횟수 (처음 3번까지 보임)
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const isWeb = Platform.OS === 'web';
const INDEX = 'chatFailed';
const ITEM = (crid: string) => `chatFailed_${crid}`;
const DICTATION = 'chatDictationSeen';
const KST_MS = 9 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

export type SavedQuestion = {
  crid: string;
  content: string;
  dismissed: boolean;
  sessionId: number | null; // 대화를 만들기 전(H-1)에 실패했으면 null
  questionId?: number;
};

const kstDay = (ms = Date.now()) => Math.floor((ms + KST_MS) / DAY_MS);

async function read(key: string): Promise<string | null> {
  try {
    if (isWeb) return globalThis.localStorage?.getItem(key) ?? null;
    return await SecureStore.getItemAsync(key);
  } catch {
    return null; // 저장소를 못 읽어도 대화는 열림 (기기에 남긴 값은 덤)
  }
}

async function write(key: string, value: string): Promise<void> {
  try {
    if (isWeb) globalThis.localStorage?.setItem(key, value);
    else await SecureStore.setItemAsync(key, value);
  } catch {
    // 못 남기면 이번 창에서만 보임
  }
}

async function remove(key: string): Promise<void> {
  try {
    if (isWeb) globalThis.localStorage?.removeItem(key);
    else await SecureStore.deleteItemAsync(key);
  } catch {
    // 다음 저장 때 목록에서 빠짐
  }
}

type Index = { day: number; crids: string[] };

async function readIndex(): Promise<Index | null> {
  const raw = await read(INDEX);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Index;
  } catch {
    return null;
  }
}

// 로그인이 끝났을 때 (같은 기기를 다른 사람이 쓸 수 있음)
export const clearFailed = () => (queue = queue.then(removeFailed));

async function removeFailed(): Promise<void> {
  const index = await readIndex();
  for (const crid of index?.crids ?? []) await remove(ITEM(crid));
  await remove(INDEX);
}

// 오늘 남긴 실패한 질문. 날이 바뀌었으면 지우고 빈 목록
export async function loadFailed(): Promise<SavedQuestion[]> {
  await queue; // 막 쓰던 값까지 읽게
  const index = await readIndex();
  if (!index) return [];
  if (index.day !== kstDay()) {
    await removeFailed();
    return [];
  }
  const items: SavedQuestion[] = [];
  for (const crid of index.crids) {
    const raw = await read(ITEM(crid));
    if (!raw) continue;
    try {
      items.push(JSON.parse(raw) as SavedQuestion);
    } catch {
      // 깨진 칸은 건너뜀
    }
  }
  return items;
}

// 지금 실패해 있는 질문 전체로 바꿔 씀 (성공한 질문은 목록에서 빠지며 지워짐). 저장이 겹치지 않게 차례로
let queue: Promise<void> = Promise.resolve();
export const saveFailed = (items: SavedQuestion[]) => (queue = queue.then(() => replaceFailed(items)));

async function replaceFailed(items: SavedQuestion[]): Promise<void> {
  const before = await readIndex();
  const keep = new Set(items.map((q) => q.crid));
  for (const crid of before?.crids ?? []) if (!keep.has(crid)) await remove(ITEM(crid));
  if (!items.length) {
    await remove(INDEX);
    return;
  }
  for (const q of items) await write(ITEM(q.crid), JSON.stringify(q));
  await write(INDEX, JSON.stringify({ day: kstDay(), crids: items.map((q) => q.crid) } satisfies Index));
}

export async function dictationSeen(): Promise<number> {
  const n = Number(await read(DICTATION));
  return Number.isFinite(n) ? n : 0;
}

export const setDictationSeen = (n: number) => write(DICTATION, String(n));
