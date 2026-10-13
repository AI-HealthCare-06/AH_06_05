// 출입증(accessToken, 60분)과 재발급권(refreshToken, 14일) 저장 (API 명세서 A-2, 10/6 결정)
// 휴대폰은 expo-secure-store. 웹에는 secure-store가 없어서 개발 확인용으로만 localStorage를 씀
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const ACCESS = 'accessToken';
const REFRESH = 'refreshToken';
const isWeb = Platform.OS === 'web';

async function read(key: string): Promise<string | null> {
  if (isWeb) return globalThis.localStorage?.getItem(key) ?? null;
  return SecureStore.getItemAsync(key);
}

async function write(key: string, value: string): Promise<void> {
  if (isWeb) {
    globalThis.localStorage?.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function remove(key: string): Promise<void> {
  if (isWeb) {
    globalThis.localStorage?.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

export const tokens = {
  getAccess: () => read(ACCESS),
  getRefresh: () => read(REFRESH),
  saveAccess: (accessToken: string) => write(ACCESS, accessToken),
  // 로그인, 회원가입 응답을 받았을 때 (재발급권은 A-4에서 새로 주지 않음)
  async save(accessToken: string, refreshToken: string) {
    await write(ACCESS, accessToken);
    await write(REFRESH, refreshToken);
  },
  // 재발급권도 끝났을 때, 그리고 나중에 탈퇴와 동의 철회 때
  async clear() {
    await remove(ACCESS);
    await remove(REFRESH);
  },
};
