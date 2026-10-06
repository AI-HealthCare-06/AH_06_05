// 챗봇 플로팅 버튼 — 아이콘만 56 원형, 새 답변 빨간 점 (설계 메모 4-1)
// 앱 루트에 떠 있음. 다른 화면은 useChatLauncher()로 숨기기 · 새 답변 표시 · 열기를 요청
import { usePathname, useRouter } from 'expo-router';
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { copy } from '@/shared/copy';
import { C, L } from '@/shared/theme';
import { ChatbotIcon } from '@/shared/ui/icons';

// 버튼을 숨기는 화면 — 챗봇 창 자체 · 촬영 · 인식 확인 · 분석 중 (경로는 화면을 만들 때 맞춤)
const HIDDEN = ['/chat', '/capture', '/recognize', '/analyzing'];
// 하단 내비가 있는 화면 — 버튼을 내비 위로 올림
const WITH_BOTTOM_NAV = ['/challenge', '/me'];

type Launcher = {
  openChat: () => void;
  setLauncherVisible: (v: boolean) => void;
  setHasNewAnswer: (v: boolean) => void;
};

const Ctx = createContext<Launcher | null>(null);

export function useChatLauncher() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useChatLauncher는 ChatLauncherProvider 안에서만 쓸 수 있어요');
  return v;
}

export function ChatLauncherProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [visible, setLauncherVisible] = useState(true);
  const [hasNew, setHasNewAnswer] = useState(false);

  const openChat = useCallback(() => {
    setHasNewAnswer(false); // 창을 열면 빨간 점이 사라짐
    router.push('/chat');
  }, [router]);

  const value = useMemo(() => ({ openChat, setLauncherVisible, setHasNewAnswer }), [openChat]);

  return (
    <Ctx.Provider value={value}>
      {children}
      {visible && <LauncherButton hasNew={hasNew} onPress={openChat} />}
    </Ctx.Provider>
  );
}

function LauncherButton({ hasNew, onPress }: { hasNew: boolean; onPress: () => void }) {
  const pathname = usePathname();
  const ins = useSafeAreaInsets();
  if (HIDDEN.some((p) => pathname.startsWith(p))) return null;
  const navHeight = WITH_BOTTOM_NAV.some((p) => pathname.startsWith(p)) ? L.bottomNav : 0;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={hasNew ? copy.chatbot.launcherNew : copy.chatbot.launcher}
      onPress={onPress}
      style={({ pressed }) => [st.fab, { bottom: ins.bottom + navHeight + L.fabGap, opacity: pressed ? 0.85 : 1 }]}
    >
      <ChatbotIcon />
      {hasNew && <View style={st.dot} />}
    </Pressable>
  );
}

const st = StyleSheet.create({
  fab: {
    position: 'absolute',
    right: 16,
    width: L.fab,
    height: L.fab,
    borderRadius: L.fab / 2,
    backgroundColor: C.p600,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: C.p600,
    shadowOpacity: 0.35,
    shadowRadius: 7,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  dot: {
    position: 'absolute',
    top: 1,
    right: 1,
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: C.danger,
    borderWidth: 2,
    borderColor: C.onPrimary,
  },
});
