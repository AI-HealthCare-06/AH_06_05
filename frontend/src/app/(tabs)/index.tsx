import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { TopNav } from '@/features/common/nav';
import { copy } from '@/shared/copy';
import { C, L, S, T } from '@/shared/theme';
import { Disclaimer } from '@/shared/ui';
import { CameraIcon } from '@/shared/ui/icons';

// CM-03-E1 처음 홈 (뼈대) — 처방 이력 · 재방문 홈(CM-03)은 API 붙일 때
export default function Home() {
  const ins = useSafeAreaInsets();
  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <TopNav current="index" />
      <ScrollView
        contentContainerStyle={{ padding: S.side, paddingBottom: ins.bottom + L.fab + L.fabGap * 2 }}
      >
        <View style={st.hero}>
          <Text style={st.heroTitle}>{copy.home.heroTitle}</Text>
          <Text style={st.heroBody}>{copy.home.heroBody}</Text>
          <Pressable accessibilityRole="button" style={({ pressed }) => [st.capture, { opacity: pressed ? 0.85 : 1 }]}>
            <CameraIcon />
            <Text style={st.captureText}>{copy.home.capture}</Text>
          </Pressable>
        </View>
        <Text style={[T.caption, { marginTop: S.section }]}>{copy.preparing}</Text>
        <Disclaimer />
      </ScrollView>
    </View>
  );
}

const st = StyleSheet.create({
  hero: { backgroundColor: C.p600, borderRadius: 20, padding: 20, gap: 14 },
  heroTitle: { fontSize: 22, fontWeight: '800', lineHeight: 29, color: C.onPrimary },
  heroBody: { fontSize: 15, lineHeight: 22, color: 'rgba(255,255,255,0.92)' },
  capture: {
    minHeight: 64,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: C.card,
    borderRadius: 14,
  },
  captureText: { fontSize: 19, fontWeight: '800', color: C.p700 },
});
