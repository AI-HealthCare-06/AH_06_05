import { Tabs } from 'expo-router';

import { BottomNav } from '@/features/common/nav';

// 홈 · 실천 · 내정보 — 아래 내비는 BottomNav가 그림 (홈에서는 숨김)
export default function TabsLayout() {
  return (
    <Tabs screenOptions={{ headerShown: false }} tabBar={(props) => <BottomNav {...props} />}>
      <Tabs.Screen name="index" />
      <Tabs.Screen name="challenge" />
      <Tabs.Screen name="me" />
    </Tabs>
  );
}
