import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { TopNav } from '@/features/common/nav';
import { useFlow } from '@/features/ocr/flow';
import { RecentRecord } from '@/features/rag/recentRecord';
import { copy } from '@/shared/copy';
import { C, L, S, T } from '@/shared/theme';
import { Disclaimer } from '@/shared/ui';
import { CameraIcon } from '@/shared/ui/icons';

// CM-03-E1 처음 홈 (뼈대) + CM-03 최근 기록 카드(기록이 있을 때만 보임). 실천 카드(P-3)는 API 붙일 때
export default function Home() {
  const ins = useSafeAreaInsets();
  const router = useRouter();
  const { reset } = useFlow();
  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <TopNav current="index" />
      <ScrollView
        contentContainerStyle={{ padding: S.side, paddingBottom: ins.bottom + L.fab + L.fabGap * 2 }}
      >
        <View style={st.hero}>
          <Text style={st.heroTitle}>{copy.home.heroTitle}</Text>
          <Text style={st.heroBody}>{copy.home.heroBody}</Text>
          <Pressable
            accessibilityRole="button"
            onPress={() => {
              reset(); // 새 처방전이므로 이전 사진 · 번호를 비움
              router.push('/capture');
            }}
            style={({ pressed }) => [st.capture, { opacity: pressed ? 0.85 : 1 }]}
          >
            <CameraIcon />
            <Text style={st.captureText}>{copy.home.capture}</Text>
          </Pressable>
        </View>
        <RecentRecord />
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
