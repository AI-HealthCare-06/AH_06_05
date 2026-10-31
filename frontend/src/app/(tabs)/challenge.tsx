import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';

import { getToday, recordCheck, recordValue } from '@/features/challenge/api';
import { CelebrateScreen } from '@/features/challenge/celebrate';
import type { Today, TodayItem } from '@/features/challenge/types';
import { useFlow } from '@/features/ocr/flow';
import { listAnalyses } from '@/features/rag/api';
import { ApiError } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { C, L, S, T } from '@/shared/theme';
import { Btn, Card, Check, Chip, Disclaimer, Screen } from '@/shared/ui';

const c = copy.challenge;
const errText = (e: unknown) => (e instanceof ApiError ? e.message : copy.common.serverError);

// RW-03 ~ RW-05 오늘의 실천 (미실천, 일부 완료, 전체 완료) · RW-03-E1 저장 실패 배너 · RW-03-E2 목표 없음
export default function Challenge() {
  const router = useRouter();
  const { setAnalysisId } = useFlow();
  const [today, setToday] = useState<Today | null>(null);
  const [error, setError] = useState<string | null>(null); // 불러오기 실패
  const [failed, setFailed] = useState<(() => Promise<void>) | null>(null); // 저장 실패: 같은 요청을 다시 보냄
  const [noAnalysis, setNoAnalysis] = useState(false);
  const [celebrate, setCelebrate] = useState(false); // 마지막 항목을 완료한 직후에만 달력과 응원 문구를 보여 줌
  const wasAll = useRef(false);
  const busy = useRef(new Set<number>());
  const { from } = useLocalSearchParams<{ from?: string }>();
  // 목표 고르기에서 넘어왔으면 뒤로가기는 그 화면으로 (목표를 더 고르거나 뺄 수 있게), 아니면 홈으로
  const toHome = () => (from === 'select' ? router.navigate('/challenge-select') : router.navigate('/'));

  const load = useCallback(async () => {
    try {
      setError(null);
      const t = await getToday();
      wasAll.current = t.totalCount > 0 && t.doneCount === t.totalCount; // 불러올 때는 보여 주지 않음
      setToday(t);
    } catch (e) {
      setError(errText(e));
    }
  }, []);

  // 탭으로 돌아올 때마다 다시 불러옴 (목표를 새로 고른 뒤, 홈에서 넘어올 때)
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  // 저장하고 서버가 돌려준 상태로 화면을 맞춤. 실패하면 배너(RW-03-E1)와 같은 요청 다시 보내기
  const save = useCallback(
    async (goalId: number, send: () => Promise<unknown>) => {
      if (busy.current.has(goalId)) return;
      busy.current.add(goalId);
      const run = async () => {
        await send();
        setFailed(null);
        const t = await getToday();
        const all = t.totalCount > 0 && t.doneCount === t.totalCount;
        if (all && !wasAll.current) setCelebrate(true);
        wasAll.current = all;
        setToday(t);
      };
      try {
        await run();
      } catch {
        setFailed(() => run);
      } finally {
        busy.current.delete(goalId);
      }
    },
    [],
  );

  const retry = async () => {
    if (!failed) return;
    try {
      await failed();
    } catch {
      // 배너가 그대로 남음
    }
  };

  // 나에게 맞는 실천 고르기: 가장 최근에 끝난 분석으로 바로 목표 고르기 화면으로 (결과 화면을 거치지 않음)
  const goPick = async () => {
    try {
      const r = await listAnalyses(null, 20);
      const last = r.items.find((i) => i.status === 'done');
      if (last) {
        setAnalysisId(last.analysisId);
        return router.push('/challenge-select');
      }
    } catch {
      // 아래 안내로
    }
    setNoAnalysis(true);
  };

  if (!today) {
    return (
      <Screen title={copy.nav.challenge} onBack={toHome} footer={error ? <Btn label={copy.common.retry} onPress={load} /> : undefined}>
        {error ? <Text style={T.body}>{error}</Text> : <ActivityIndicator color={C.p600} style={{ marginTop: 40 }} />}
      </Screen>
    );
  }
  // RW-03-E2: 아래 고정 버튼은 챗봇 버튼과 겹쳐서 본문 안에 둠
  if (!today.hasGoals) {
    return (
      <Screen title={copy.nav.challenge} onBack={toHome}>
        <Card style={{ gap: 6 }}>
          <Text style={T.subhead}>{noAnalysis ? c.noAnalysisTitle : c.emptyToday}</Text>
          <Text style={T.body}>{noAnalysis ? c.noAnalysisBody : c.emptyTodayBody}</Text>
        </Card>
        <View style={{ marginTop: 16 }}>
          {noAnalysis ? <Btn label={c.goCapture} onPress={() => router.navigate('/')} /> : <Btn label={c.goPick} onPress={goPick} />}
        </View>
        <Disclaimer />
        <View style={{ height: L.fab + L.fabGap }} />
      </Screen>
    );
  }
  const all = today.totalCount > 0 && today.doneCount === today.totalCount;
  return (
    <Screen title={copy.nav.challenge} onBack={toHome}>
      <CelebrateScreen
        visible={celebrate}
        streakDays={today.streakDays}
        onHome={() => {
          setCelebrate(false);
          router.navigate('/');
        }}
      />
      {failed && (
        <Card tone="danger" style={{ gap: 8, marginBottom: 12 }}>
          <Text style={T.subhead} accessibilityLiveRegion="assertive">
            {c.saveFail}
          </Text>
          <Text style={T.body}>{c.saveFailBody}</Text>
          <Btn label={copy.common.retry} onPress={retry} />
        </Card>
      )}
      <Text style={T.heading} accessibilityRole="header">
        {c.todayTitle}
      </Text>
      <Card style={{ marginTop: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <Text style={[T.subhead, { flexShrink: 1 }]}>{c.progress(today.doneCount, today.totalCount)}</Text>
        <Chip label={all ? c.allDoneChip : today.streakDays > 0 ? c.streak(today.streakDays) : c.notDone} tone={all ? 'info' : 'neutral'} />
      </Card>
      <View style={{ gap: S.gap, marginTop: S.gap }}>
        {today.items.map((it) => (
          <GoalCard
            key={it.goalId}
            item={it}
            onCheck={() => save(it.goalId, () => recordCheck(it.goalId, !it.done))}
            onValue={(v) => save(it.goalId, () => recordValue(it.goalId, v))}
          />
        ))}
      </View>
      <Pressable accessibilityRole="link" onPress={goPick} style={{ minHeight: L.touch, justifyContent: 'center', alignSelf: 'flex-start', marginTop: 8 }}>
        <Text style={[T.bodyM, { color: C.p700 }]}>{c.rePick}</Text>
      </Pressable>
      {noAnalysis && <Text style={[T.caption, { color: C.danger }]}>{c.noAnalysisTitle}</Text>}
      <Disclaimer />
      <View style={{ height: L.fab + L.fabGap }} />
    </Screen>
  );
}

// 목표 한 칸: 앞의 네모를 누르면 체크, 다시 누르면 취소 (목표 고르기 화면과 같은 체크 부품)
// 수량형(걷기)은 체크하면 목표량을 채운 것으로, 취소하면 0으로 저장
function GoalCard({ item, onCheck, onValue }: { item: TodayItem; onCheck: () => void; onValue: (v: number) => void }) {
  const qty = item.goalType === 'quantity';
  const press = () => (qty ? onValue(item.done ? 0 : (item.targetValue ?? 0)) : onCheck());
  return (
    <Card style={{ gap: 4 }}>
      <Check on={item.done} label={item.title} bold onPress={press} />
      {!!item.desc && <Text style={[T.body, { color: C.text2 }]}>{item.desc}</Text>}
      {item.cautionLabel && <Chip label={item.cautionLabel} tone="caution" />}
    </Card>
  );
}
