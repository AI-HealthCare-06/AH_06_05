import { useRouter } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';

import { useFlow } from '@/features/ocr/flow';
import { getAnalysisStatus, retryAnalysis, startAnalysis } from '@/features/rag/api';
import type { AnalysisProgress, StepState } from '@/features/rag/types';
import { ApiError } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { C, T } from '@/shared/theme';
import { Btn, Card, Chip } from '@/shared/ui';
import { Screen } from '@/shared/ui';

const a = copy.analyzing;
const TONE: Record<StepState, 'success' | 'info' | 'neutral' | 'danger'> = { done: 'success', running: 'info', pending: 'neutral', failed: 'danger' };
const KEYS = ['drug_info', 'safety_check', 'guide_generation'];

// RG-01 분석 중, RG-01-E1 분석 실패 (R-1 시작, R-2 2초마다 확인, R-3 다시 시도)
export default function Analyzing() {
  const router = useRouter();
  const { prescriptionIds, analysisId, setAnalysisId } = useFlow();
  const [progress, setProgress] = useState<AnalysisProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [run, setRun] = useState(0); // 다시 시도할 때마다 올려서 확인을 다시 시작
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (analysisId !== null) return; // 결과 화면에서 다시 시도로 돌아온 경우: 이미 있는 분석을 이어서 확인
    if (prescriptionIds.length === 0) return;
    startAnalysis(prescriptionIds)
      .then((v) => setAnalysisId(v.analysisId))
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : copy.common.serverError));
  }, [analysisId, prescriptionIds, setAnalysisId]);

  useEffect(() => {
    if (analysisId === null) return;
    let live = true;
    const tick = async () => {
      try {
        const p = await getAnalysisStatus(analysisId);
        if (!live) return;
        setProgress(p);
        if (p.status === 'done') router.replace('/result');
        else if (p.status !== 'failed') timer = setTimeout(tick, 2000);
      } catch (e) {
        if (live) setError(e instanceof ApiError ? e.message : copy.common.serverError);
      }
    };
    let timer: ReturnType<typeof setTimeout> = setTimeout(tick, 0);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [analysisId, run, router]);

  const retry = useCallback(async () => {
    if (analysisId === null) return;
    try {
      setError(null);
      await retryAnalysis(analysisId);
      setProgress(null);
      setRun((n) => n + 1);
    } catch (e) {
      setError(e instanceof ApiError && e.code === 'RETRY_LIMIT_EXCEEDED' ? a.limit : e instanceof ApiError ? e.message : copy.common.serverError);
    }
  }, [analysisId]);

  if (prescriptionIds.length === 0) {
    return (
      <Screen title={a.title} back={false} footer={<Btn label={a.goCapture} onPress={() => router.replace('/capture')} />}>
        <Text style={T.body}>{a.noPrescription}</Text>
      </Screen>
    );
  }

  const stateOf = (i: number): StepState => progress?.steps.find((s) => s.key === KEYS[i])?.state ?? (i === 0 ? 'running' : 'pending');
  const failed = progress?.status === 'failed';

  return (
    <Screen
      title={a.title}
      back={false}
      footer={
        failed || error ? (
          <View style={{ gap: 8 }}>
            <Btn label={a.retry} onPress={retry} />
            {progress?.partialResultAvailable && <Btn label={a.partial} kind="secondary" onPress={() => router.replace('/result')} />}
            <Btn label={a.home} kind="ghost" onPress={() => router.replace('/')} />
          </View>
        ) : (
          <Btn label={a.toHome} kind="secondary" onPress={() => router.replace('/')} />
        )
      }
    >
      <Text style={T.title}>{failed ? a.failHead : a.head}</Text>
      <Text style={[T.body, { color: C.text2, marginTop: 4 }]}>{failed ? a.failBody : a.wait}</Text>
      {error && <Text style={[T.body, { color: C.danger, marginTop: 8 }]}>※ {error}</Text>}

      <View style={{ gap: 10, marginTop: 20 }}>
        {KEYS.map((k, i) => {
          const s = stateOf(i);
          return (
            <Card key={k} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 }}>
                {s === 'running' ? <ActivityIndicator color={C.p600} /> : <Text style={{ fontSize: 16, width: 20, textAlign: 'center', fontWeight: '800', color: s === 'done' ? C.success : s === 'failed' ? C.danger : C.text2 }}>{i + 1}</Text>}
                <Text style={[T.bodyM, { flex: 1 }]}>{failed ? a.stepsDone[i] : a.steps[i]}</Text>
              </View>
              <Chip label={a.state[s]} tone={TONE[s]} />
            </Card>
          );
        })}
      </View>

      {progress?.drugCount !== undefined && !failed && (
        <Card style={{ marginTop: 16, gap: 4 }}>
          <Text style={T.label}>{a.drugs(progress.drugCount, progress.excludedCount ?? 0)}</Text>
        </Card>
      )}
      <Text style={[T.caption, { marginTop: 12 }]}>{failed ? a.failNote : a.keepGoing}</Text>
    </Screen>
  );
}
