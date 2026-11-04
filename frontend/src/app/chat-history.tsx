import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';

import { getChatDays } from '@/features/chatbot/api';
import { dayLabel, kstToday, monthGrid } from '@/features/chatbot/time';
import { copy } from '@/shared/copy';
import { C, L, T } from '@/shared/theme';
import { Btn, Card, Screen } from '@/shared/ui';

const c = copy.chatbot;
const CELL = 44; // 날짜 칸. 좁은 화면에서도 한 줄에 7칸이 들어가야 해서 48의 예외 (설계 메모 4-12)
const WIDTH = `${100 / 7}%` as const;

const ym = (y: number, m: number) => `${y}-${String(m).padStart(2, '0')}`;

function Arrow({ label, text, onPress }: { label: string; text: string; onPress?: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !onPress }}
      onPress={onPress}
      style={{ width: L.touch, height: L.touch, alignItems: 'center', justifyContent: 'center', opacity: onPress ? 1 : 0.3 }}
    >
      <Text style={[T.heading, { color: C.text2 }]}>{text}</Text>
    </Pressable>
  );
}

function Dot({ color, label, ring = false }: { color: string; label: string; ring?: boolean }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
      <View style={{ width: 12, height: 12, borderRadius: 6, backgroundColor: ring ? 'transparent' : color, borderWidth: ring ? 2 : 0, borderColor: color }} />
      <Text style={T.caption}>{label}</Text>
    </View>
  );
}

// CB-02 대화 기록, 달력 (설계 메모 4-12, 명세서 H-4 ?month=). 날짜는 대화를 시작한 날
export default function ChatHistory() {
  const router = useRouter();
  const { current } = useLocalSearchParams<{ current?: string }>();
  const today = kstToday();
  const [thisYear, thisMonth] = today.split('-').map(Number);
  const [{ y, m }, setShown] = useState({ y: thisYear, m: thisMonth });
  const [dates, setDates] = useState<string[]>([]);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');

  const load = useCallback(() => {
    let alive = true;
    setState('loading');
    getChatDays(ym(y, m))
      .then((list) => {
        if (!alive) return;
        setDates(list);
        setState('ready');
      })
      .catch(() => alive && setState('error'));
    return () => {
      alive = false;
    };
  }, [y, m]);

  // 목록에서 지우고 돌아오면 그 날짜 표시도 사라지게 다시 읽음
  useFocusEffect(load);

  const move = (step: number) =>
    setShown(({ y: yy, m: mm }) => {
      const n = mm + step;
      return n < 1 ? { y: yy - 1, m: 12 } : n > 12 ? { y: yy + 1, m: 1 } : { y: yy, m: n };
    });
  const isThisMonth = y === thisYear && m === thisMonth;
  const { blanks, days } = monthGrid(y, m);

  return (
    <Screen title={c.historyTitle}>
      <View style={{ gap: 12 }}>
        <Text style={T.body}>{c.historyGuide}</Text>
        <Card style={{ gap: 8 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <Arrow label={c.prevMonth} text="‹" onPress={() => move(-1)} />
            <Text style={T.heading} accessibilityRole="header">
              {c.month(y, m)}
            </Text>
            <Arrow label={c.nextMonth} text="›" onPress={isThisMonth ? undefined : () => move(1)} />
          </View>
          <View style={{ flexDirection: 'row' }}>
            {c.weekdays.map((w) => (
              <Text key={w} style={[T.caption, { width: WIDTH, textAlign: 'center' }]}>
                {w}
              </Text>
            ))}
          </View>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
            {Array.from({ length: blanks }, (_, i) => (
              <View key={`b${i}`} style={{ width: WIDTH, height: CELL }} />
            ))}
            {Array.from({ length: days }, (_, i) => {
              const date = `${ym(y, m)}-${String(i + 1).padStart(2, '0')}`;
              const has = dates.includes(date);
              const isToday = date === today;
              return (
                <Pressable
                  key={date}
                  accessibilityRole="button"
                  accessibilityLabel={c.dayA11y(dayLabel(date), has)}
                  accessibilityState={{ disabled: !has }}
                  onPress={has ? () => router.push({ pathname: '/chat-history-day', params: { date, current: current ?? '' } }) : undefined}
                  style={{ width: WIDTH, height: CELL, alignItems: 'center', justifyContent: 'center' }}
                >
                  {/* 오늘은 테두리, 기록 있음은 채움. 전에는 오늘을 진하게 채워 기록이 없어 눌리지 않는 날도 눌릴 것처럼 보였음 (11/4 E2E) */}
                  <View style={{ width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center', backgroundColor: has ? C.p100 : 'transparent', borderWidth: isToday ? 2 : 0, borderColor: C.p600 }}>
                    <Text style={{ fontSize: 16, fontWeight: has || isToday ? '700' : '400', color: has || isToday ? C.p700 : C.text3 }}>{i + 1}</Text>
                  </View>
                </Pressable>
              );
            })}
          </View>
          <View style={{ flexDirection: 'row', gap: 16, paddingTop: 4 }}>
            <Dot color={C.p100} label={c.legendHas} />
            <Dot color={C.p600} label={c.legendToday} ring />
          </View>
        </Card>
        {state === 'loading' && <ActivityIndicator color={C.p600} />}
        {state === 'ready' && dates.length === 0 && <Text style={[T.body, { color: C.text2, textAlign: 'center' }]}>{c.historyEmpty}</Text>}
        {state === 'error' && (
          <View style={{ gap: 8 }}>
            <Text style={[T.body, { color: C.danger }]}>{c.historyFail}</Text>
            <Btn label={c.reload} kind="secondary" onPress={load} />
          </View>
        )}
      </View>
    </Screen>
  );
}
