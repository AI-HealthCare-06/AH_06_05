import { useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';

import { createGoals, getRecommendations, getToday } from '@/features/challenge/api';
import type { RecommendationList } from '@/features/challenge/types';
import { useFlow } from '@/features/ocr/flow';
import { ApiError } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { C, T } from '@/shared/theme';
import { Btn, Card, Check, Chip, Disclaimer, Screen } from '@/shared/ui';

const c = copy.challenge;
const MAX = 3;
const errText = (e: unknown) => (e instanceof ApiError ? e.message : copy.common.serverError);

// RW-02 실천 목표 선택 (P-1 추천 → P-2 목표 만들기). RG-05 [이 목표로 실천 시작하기]에서 들어옴
export default function ChallengeSelect() {
  const router = useRouter();
  const { analysisId } = useFlow();
  const [data, setData] = useState<RecommendationList | null>(null);
  const [picked, setPicked] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [limit, setLimit] = useState(false);

  const load = useCallback(async () => {
    if (analysisId === null) return;
    try {
      setError(null);
      const list = await getRecommendations(analysisId);
      setData(list);
      // 이미 정한 목표가 있으면 미리 골라 둠 (더 고르거나 뺄 수 있게). 못 불러와도 빈 선택으로 시작
      try {
        const t = await getToday();
        const titles = new Set(t.items.map((i) => i.title));
        setPicked(list.items.filter((i) => titles.has(i.title)).map((i) => i.id).slice(0, MAX));
      } catch {
        // 선택 없음
      }
    } catch (e) {
      setError(errText(e));
    }
  }, [analysisId]);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = (id: number) => {
    if (picked.includes(id)) {
      setLimit(false);
      return setPicked(picked.filter((x) => x !== id));
    }
    if (picked.length >= MAX) return setLimit(true);
    setLimit(false);
    setPicked([...picked, id]);
  };

  const begin = async () => {
    if (saving || picked.length === 0) return;
    setSaving(true);
    try {
      setError(null);
      await createGoals(picked);
      router.push({ pathname: '/challenge', params: { from: 'select' } });
    } catch (e) {
      setError(errText(e));
      setSaving(false);
    }
  };

  const backToResult = () => router.push('/result'); // 질환 고르기는 결과 화면의 생활습관 탭

  if (analysisId === null) {
    return (
      <Screen title={c.selectTitle} footer={<Btn label={copy.common.goHome} onPress={() => router.replace('/')} />}>
        <Card style={{ gap: 6 }}>
          <Text style={T.subhead}>{c.noAnalysisTitle}</Text>
          <Text style={T.body}>{c.noAnalysisBody}</Text>
        </Card>
      </Screen>
    );
  }
  if (!data) {
    return (
      <Screen title={c.selectTitle} footer={error ? <Btn label={copy.common.retry} onPress={load} /> : undefined}>
        {error ? <Text style={T.body}>{error}</Text> : <ActivityIndicator color={C.p600} style={{ marginTop: 40 }} />}
      </Screen>
    );
  }
  // 질환이 없으면 질환 고르기(RG-05-E1)로, 질환은 있는데 근거가 없으면 추천 없음 안내
  if (data.items.length === 0) {
    const title = data.hasDiseases ? c.emptyTitle : c.noDiseaseTitle;
    const body = data.hasDiseases ? c.emptyBody : c.noDiseaseBody;
    return (
      <Screen title={c.selectTitle} footer={<Btn label={c.backToResult} onPress={backToResult} />}>
        <Card tone="caution" style={{ gap: 6 }}>
          <Text style={T.subhead}>{title}</Text>
          <Text style={T.body}>{body}</Text>
        </Card>
        <Disclaimer />
      </Screen>
    );
  }
  return (
    <Screen
      title={c.selectTitle}
      footer={
        <View style={{ gap: 8 }}>
          {error && <Text style={[T.caption, { color: C.danger }]}>{error}</Text>}
          <Btn label={c.begin} disabled={picked.length === 0 || saving} onPress={begin} />
        </View>
      }
    >
      <Text style={T.heading} accessibilityRole="header">
        {c.selectHead}
      </Text>
      <Text style={[T.body, { color: C.text2, marginTop: 4, marginBottom: 16 }]}>{c.selectBody}</Text>
      <View style={{ gap: 12 }}>
        {data.items.map((it) => {
          const on = picked.includes(it.id);
          return (
            <Card key={it.id} style={{ gap: 4, borderWidth: on ? 2 : 1, borderColor: on ? C.p600 : C.border }}>
              <Check on={on} label={it.title} bold onPress={() => toggle(it.id)} />
              <Text style={[T.body, { color: C.text2 }]}>{it.desc}</Text>
              {it.cautionLabel && <Chip label={it.cautionLabel} tone="caution" />}
            </Card>
          );
        })}
      </View>
      <Text style={[T.caption, { marginTop: 12, color: limit ? C.danger : C.text2 }]} accessibilityLiveRegion="polite">
        {limit ? c.max : c.picked(picked.length)}
      </Text>
      <Disclaimer />
    </Screen>
  );
}
