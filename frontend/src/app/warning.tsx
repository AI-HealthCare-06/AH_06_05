import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';

import { useChatLauncher } from '@/features/chatbot/launcher';
import { useFlow } from '@/features/ocr/flow';
import { getWarning } from '@/features/rag/api';
import type { WarningDetail } from '@/features/rag/types';
import { ApiError } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { C, T } from '@/shared/theme';
import { Btn, Card, Chip, Disclaimer, Screen, Section } from '@/shared/ui';

const r = copy.result;

// RG-03 경고 자세히 보기 (R-5)
export default function WarningScreen() {
  const router = useRouter();
  const { openChat } = useChatLauncher();
  const { analysisId } = useFlow();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [w, setW] = useState<WarningDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [run, setRun] = useState(0);

  useEffect(() => {
    if (analysisId === null || !id) return;
    let live = true;
    setError(null);
    getWarning(analysisId, Number(id))
      .then((v) => live && setW(v))
      .catch((e: unknown) => live && setError(e instanceof ApiError ? e.message : copy.common.serverError));
    return () => {
      live = false;
    };
  }, [analysisId, id, run]);

  if (!w) {
    return (
      <Screen
        title={r.warningTitle}
        footer={error || analysisId === null ? <Btn label={error ? copy.common.retry : copy.common.goHome} onPress={error ? () => setRun((n) => n + 1) : () => router.replace('/')} /> : undefined}
      >
        {error ? <Text style={[T.body, { color: C.danger }]}>{r.loadFail} · {error}</Text> : <ActivityIndicator color={C.p600} style={{ marginTop: 40 }} />}
      </Screen>
    );
  }
  const tone = w.severity;
  return (
    <Screen
      title={r.warningTitle}
      footer={<Btn label={r.askWarning} onPress={() => openChat({ from: 'RG-03', analysisId: analysisId ?? undefined, context: { type: 'warning', id: w.id } })} />}
    >
      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
        <Chip label={r.severity[tone]} tone={tone} />
        <Text style={[T.heading, { flex: 1 }]}>{w.title}</Text>
      </View>
      <Text style={[T.body, { marginTop: 10 }]}>{r.together(w.drugs.length)}</Text>
      <View style={{ gap: 10, marginTop: 12 }}>
        {w.drugs.map((d, i) => (
          <Card key={i}>
            <Text style={T.bodyM}>{d.itemName}</Text>
            <Text style={T.caption}>{[d.hospitalName, d.category, d.ingredient && `성분 ${d.ingredient}`].filter(Boolean).join(' · ')}</Text>
          </Card>
        ))}
      </View>
      <Section title={r.whyTitle}>
        <Card>
          <Text style={T.body}>{w.explanation}</Text>
          <Text style={[T.caption, { marginTop: 8 }]}>{r.original(w.reasonOriginal)}</Text>
        </Card>
      </Section>
      <Section title={r.sourceTitle}>
        <Card style={{ gap: 6 }}>
          <Text style={T.body}>{w.source.name}{w.source.noticeDate ? ` (고시일 ${w.source.noticeDate})` : ''}</Text>
          <Text style={T.caption}>{r.judged}</Text>
        </Card>
      </Section>
      <Text style={[T.caption, { marginTop: 16 }]}>※ {w.actionAdvice}</Text>
      <Disclaimer />
    </Screen>
  );
}
