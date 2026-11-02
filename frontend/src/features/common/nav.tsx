// 내비 — 모든 탭 화면이 하단 내비 3개를 씀. 홈 위쪽은 앱 이름 줄만 (11/2 멘토 피드백: 홈만 상단 탭이라 이동하면 위치가 바뀌어 헷갈림, 10/2 결정을 바꿈)
import { Tabs } from 'expo-router';
import type { ComponentProps, ComponentType } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { copy } from '@/shared/copy';
import { C, L } from '@/shared/theme';
import { ChallengeIcon, HomeIcon, MeIcon } from '@/shared/ui/icons';

export type TabName = 'index' | 'challenge' | 'me';

type BottomTabBarProps = Parameters<NonNullable<ComponentProps<typeof Tabs>['tabBar']>>[0];

const TABS: { name: TabName; href: '/' | '/challenge' | '/me'; label: string; Icon: ComponentType<{ color?: string }> }[] = [
  { name: 'index', href: '/', label: copy.nav.home, Icon: HomeIcon },
  { name: 'challenge', href: '/challenge', label: copy.nav.challenge, Icon: ChallengeIcon },
  { name: 'me', href: '/me', label: copy.nav.me, Icon: MeIcon },
];

// 홈 위쪽 — 앱 이름 줄 56만. 탭은 다른 화면과 같은 하단 내비
export function TopNav() {
  const ins = useSafeAreaInsets();
  return (
    <View style={[st.top, { paddingTop: ins.top }]}>
      <View style={st.titleRow}>
        <View style={st.logo}>
          <Text style={st.logoText}>약</Text>
        </View>
        <Text style={st.appName} accessibilityRole="header">
          {copy.appName}
        </Text>
      </View>
    </View>
  );
}

// 탭 화면 아래쪽 — 높이 64, 아이콘 22 + 글자 13. 홈 포함 모든 탭 화면
export function BottomNav({ state, navigation }: BottomTabBarProps) {
  const ins = useSafeAreaInsets();
  const current = state.routes[state.index]?.name;
  return (
    <View
      style={[st.bottom, { height: L.bottomNav + ins.bottom, paddingBottom: ins.bottom }]}
      accessibilityRole="tablist"
      accessibilityLabel={copy.nav.menu}
    >
      {TABS.map((t) => {
        const on = t.name === current;
        const color = on ? C.p600 : C.text3;
        return (
          <Pressable
            key={t.name}
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            accessibilityLabel={t.label}
            onPress={() => !on && navigation.navigate(t.name)}
            style={st.bottomTab}
          >
            <t.Icon color={color} />
            <Text style={[st.bottomLabel, { color, fontWeight: on ? '700' : '400' }]}>{t.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  top: { backgroundColor: C.card, borderBottomWidth: 1, borderBottomColor: C.border },
  titleRow: { height: 56, flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 20 },
  logo: { width: 30, height: 30, borderRadius: 9, backgroundColor: C.p600, alignItems: 'center', justifyContent: 'center' },
  logoText: { color: C.onPrimary, fontSize: 15, fontWeight: '800' },
  appName: { flex: 1, fontSize: 17, fontWeight: '800', color: C.text },
  bottom: { flexDirection: 'row', backgroundColor: C.card, borderTopWidth: 1, borderTopColor: C.border },
  bottomTab: { flex: 1, minHeight: L.bottomNav, alignItems: 'center', justifyContent: 'center', gap: 4 },
  bottomLabel: { fontSize: L.navLabel },
});
