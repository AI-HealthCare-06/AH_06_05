// CM-03 홈의 최근 기록 카드 (R-7을 size=1로 불러 최근 1건). 기록이 없으면 여기에 기록이 생긴다는 안내 (11/2 멘토 피드백)
import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { copy } from '@/shared/copy';
import { C, R, S, T } from '@/shared/theme';

import { listAnalyses } from './api';
import { RecordCard, useOpenRecord } from './history';
import type { AnalysisListItem } from './types';

const h = copy.history;

export function RecentRecord() {
  const router = useRouter();
  const open = useOpenRecord();
  const [item, setItem] = useState<AnalysisListItem | null>(null);
  const [loaded, setLoaded] = useState(false); // 불러오기 전에는 빈 안내를 깜빡이지 않게

  // 홈으로 돌아올 때마다 다시 불러옴 (방금 끝났거나 지운 기록이 바로 반영되게). 실패하면 카드만 숨김
  useFocusEffect(
    useCallback(() => {
      let live = true;
      listAnalyses(null, 1)
        .then((r) => live && (setItem(r.items[0] ?? null), setLoaded(true)))
        .catch(() => live && (setItem(null), setLoaded(false))); // 못 불러오면 빈 안내도 숨김 (기록이 있을 수 있음)
      return () => {
        live = false;
      };
    }, []),
  );

  if (!item) {
    if (!loaded) return null;
    return (
      <View style={{ marginTop: S.section, gap: S.gap }}>
        <Text style={T.subhead} accessibilityRole="header">
          {h.recent}
        </Text>
        <View style={{ backgroundColor: C.card, borderRadius: R.card, borderWidth: 1, borderColor: C.border, borderStyle: 'dashed', padding: S.side, gap: 4 }}>
          <Text style={T.bodyM}>{h.recentEmptyTitle}</Text>
          <Text style={[T.body, { color: C.text2 }]}>{h.recentEmptyBody}</Text>
        </View>
      </View>
    );
  }
  return (
    <View style={{ marginTop: S.section, gap: S.gap }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text style={T.subhead} accessibilityRole="header">
          {h.recent}
        </Text>
        <Pressable accessibilityRole="link" hitSlop={8} onPress={() => router.push('/history')} style={{ minHeight: 48, justifyContent: 'center' }}>
          <Text style={{ fontSize: 16, fontWeight: '700', color: C.p700 }}>{h.seeAll}</Text>
        </Pressable>
      </View>
      <RecordCard item={item} onPress={() => open(item)} />
    </View>
  );
}
