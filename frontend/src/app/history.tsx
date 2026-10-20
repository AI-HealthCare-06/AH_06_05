import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';

import { useChatLauncher } from '@/features/chatbot/launcher';
import { useFlow } from '@/features/ocr/flow';
import { RecordCard, useOpenRecord } from '@/features/rag/history';
import { deleteAnalysis, listAnalyses } from '@/features/rag/api';
import type { AnalysisListItem } from '@/features/rag/types';
import { ApiError } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { C, T } from '@/shared/theme';
import { Btn, Confirm, Screen } from '@/shared/ui';

const h = copy.history;

// CM-04 지난 기록 (R-7 더 보기 방식) · CM-04-E1 삭제 확인 (R-8) · CM-04-E2 기록 없음
export default function History() {
  const router = useRouter();
  const open = useOpenRecord();
  const { reset } = useFlow();
  const { setLauncherVisible } = useChatLauncher();
  const [items, setItems] = useState<AnalysisListItem[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [more, setMore] = useState(false);
  const [target, setTarget] = useState<AnalysisListItem | null>(null); // 삭제 확인 중인 기록
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setState('loading');
      const r = await listAnalyses(null);
      setItems(r.items);
      setNext(r.nextCursor);
      setState('ready');
    } catch {
      setState('error');
    }
  }, []);

  // 결과를 보고 돌아왔을 때도 다시 불러옴 (분석이 끝났거나 지운 기록이 바로 반영되게)
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const loadMore = async () => {
    if (!next || more) return;
    try {
      setMore(true);
      const r = await listAnalyses(next);
      setItems((cur) => [...cur, ...r.items.filter((n) => !cur.some((c) => c.analysisId === n.analysisId))]);
      setNext(r.nextCursor);
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : h.loadFail);
    } finally {
      setMore(false);
    }
  };

  const confirmDelete = async () => {
    if (!target) return;
    const id = target.analysisId;
    setTarget(null);
    try {
      await deleteAnalysis(id);
      setNotice(null);
      setItems((cur) => cur.filter((c) => c.analysisId !== id));
    } catch (e) {
      if (e instanceof ApiError && e.code === 'ANALYSIS_RUNNING') setNotice(h.running);
      else if (e instanceof ApiError && e.status === 404) setItems((cur) => cur.filter((c) => c.analysisId !== id)); // 이미 없는 기록이면 목록에서만 뺌
      else setNotice(e instanceof ApiError ? e.message : copy.common.serverError);
    }
  };

  const goHome = () => router.replace('/');

  // 아래 고정 버튼이 있는 상태(기록 없음, 불러오기 실패)에서는 챗봇 버튼이 그 버튼을 가리므로 숨김
  const footerShown = state === 'error' || (state === 'ready' && items.length === 0);
  useEffect(() => {
    setLauncherVisible(!footerShown);
    return () => setLauncherVisible(true);
  }, [footerShown, setLauncherVisible]);

  if (state === 'loading' && items.length === 0) {
    return (
      <Screen title={h.title}>
        <ActivityIndicator color={C.p600} style={{ marginTop: 40 }} />
      </Screen>
    );
  }
  if (state === 'error') {
    return (
      <Screen title={h.title} footer={<Btn label={copy.common.retry} onPress={load} />}>
        <Text style={[T.body, { color: C.danger }]}>{h.loadFail}</Text>
      </Screen>
    );
  }
  if (items.length === 0) {
    // CM-04-E2 기록 없음
    return (
      <Screen
        title={h.title}
        footer={
          <Btn
            label={copy.home.capture}
            onPress={() => {
              reset(); // 새 처방전이므로 이전 분석 번호를 비움
              router.push('/capture');
            }}
          />
        }
      >
        <View style={{ alignItems: 'center', gap: 8, marginTop: 40 }}>
          <Text style={[T.heading, { textAlign: 'center' }]}>{h.emptyHead}</Text>
          <Text style={[T.body, { color: C.text2, textAlign: 'center' }]}>{h.emptyBody}</Text>
        </View>
        {notice ? <Text style={[T.body, { color: C.danger, marginTop: 16 }]}>{notice}</Text> : null}
        <Btn label={copy.common.goHome} kind="ghost" onPress={goHome} style={{ marginTop: 16 }} />
      </Screen>
    );
  }

  return (
    <Screen title={h.title}>
      {notice ? <Text style={[T.body, { color: C.danger, marginBottom: 12 }]}>{notice}</Text> : null}
      <View style={{ gap: 12 }}>
        {items.map((item) => (
          <RecordCard
            key={item.analysisId}
            item={item}
            onPress={() => open(item)}
            right={
              <Btn
                label={h.delete}
                kind="ghost"
                onPress={() => setTarget(item)}
                style={{ alignSelf: 'flex-end' }}
              />
            }
          />
        ))}
      </View>
      {next ? <Btn label={h.more} kind="secondary" disabled={more} onPress={loadMore} style={{ marginTop: 16 }} /> : null}
      <Confirm
        visible={target !== null}
        title={h.confirmTitle}
        body={h.confirmBody}
        ok={h.confirmOk}
        onOk={confirmDelete}
        onCancel={() => setTarget(null)}
      />
    </Screen>
  );
}
