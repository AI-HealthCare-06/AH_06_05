// CM-03 홈의 오늘의 실천 카드 (P-3). 최근 기록 아래에 같은 구성(제목 + 링크, 아래 카드)으로 둠. 목표가 없거나 조회가 실패하면 보이지 않음
import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { copy } from '@/shared/copy';
import { C, S, T } from '@/shared/theme';
import { Card, Chip } from '@/shared/ui';

import { getToday } from './api';
import type { Today } from './types';

const c = copy.challenge;

export function HomeChallengeCard() {
  const router = useRouter();
  const [today, setToday] = useState<Today | null>(null);

  useFocusEffect(
    useCallback(() => {
      let live = true;
      getToday()
        .then((r) => live && setToday(r))
        .catch(() => live && setToday(null));
      return () => {
        live = false;
      };
    }, []),
  );

  if (!today || !today.hasGoals) return null;
  const go = () => router.navigate('/challenge');
  const all = today.doneCount === today.totalCount;
  return (
    <View style={{ marginTop: S.section, gap: S.gap }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text style={T.subhead} accessibilityRole="header">
          {c.homeTitle}
        </Text>
        <Pressable accessibilityRole="link" hitSlop={8} onPress={go} style={{ minHeight: 48, justifyContent: 'center' }}>
          <Text style={{ fontSize: 16, fontWeight: '700', color: C.p700 }}>{c.homeSee}</Text>
        </Pressable>
      </View>
      <Card onPress={go} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <Text style={[T.subhead, { flexShrink: 1 }]}>{c.progress(today.doneCount, today.totalCount)}</Text>
        <Chip label={all ? c.allDoneChip : today.streakDays > 0 ? c.streak(today.streakDays) : c.notDone} tone={all ? 'info' : 'neutral'} />
      </Card>
    </View>
  );
}
