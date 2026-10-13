import { useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';

import { useChatLauncher } from '@/features/chatbot/launcher';
import { useFlow } from '@/features/ocr/flow';
import { PICKABLE_DISEASES } from '@/features/rag/diseases';
import { getAnalysis, putDiseases, retryAnalysis } from '@/features/rag/api';
import type { Action, AnalysisResult, Severity, Warning } from '@/features/rag/types';
import { ApiError } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { C, R, T } from '@/shared/theme';
import { Btn, Card, Chip, Disclaimer, Radio, Screen, Section } from '@/shared/ui';

const r = copy.result;
type TabKey = 'safety' | 'med' | 'life';
type Lifestyle = AnalysisResult['lifestyle'];
const SEV_TONE: Record<Severity, 'danger' | 'caution' | 'info'> = { danger: 'danger', caution: 'caution', info: 'info' };
const link = { color: C.p700, fontWeight: '600' as const, marginTop: 8, fontSize: 16 };
const errText = (e: unknown) => (e instanceof ApiError ? e.message : copy.common.serverError);

// RG-02 · RG-02-E1 안전성 / RG-04 복약 안내 / RG-05 · RG-05-E1 생활습관 (R-4 한 번에 받아서 탭만 바꿈)
export default function Result() {
  const router = useRouter();
  const { openChat } = useChatLauncher();
  const { analysisId } = useFlow();
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>('safety');

  const load = useCallback(async () => {
    if (analysisId === null) return;
    try {
      setError(null);
      setData(await getAnalysis(analysisId));
    } catch (e) {
      if (e instanceof ApiError && e.code === 'ANALYSIS_NOT_READY') return router.replace('/analyzing'); // 아직 진행 중 → RG-01
      setError(errText(e));
    }
  }, [analysisId, router]);

  useEffect(() => {
    load();
  }, [load]);

  if (analysisId === null) {
    return (
      <Screen title={r.title} back={false} footer={<Btn label={copy.common.goHome} onPress={() => router.replace('/')} />}>
        <Text style={T.body}>{r.loadFail}</Text>
      </Screen>
    );
  }
  if (!data) {
    return (
      <Screen
        title={r.title}
        back={false}
        footer={error ? <Btn label={copy.common.retry} onPress={load} /> : undefined}
      >
        {error ? <Text style={[T.body, { color: C.danger }]}>{r.loadFail} · {error}</Text> : <ActivityIndicator color={C.p600} style={{ marginTop: 40 }} />}
      </Screen>
    );
  }

  const { summary } = data;
  const counts = summary.warningCounts;
  const sev = [counts.danger && `${r.severity.danger} ${counts.danger}`, counts.caution && `${r.severity.caution} ${counts.caution}`, counts.info && `${r.severity.info} ${counts.info}`].filter(Boolean).join(' · ');
  const tabs: [TabKey, string][] = [['safety', r.tabs.safety], ['med', r.tabs.med], ['life', r.tabs.life]];
  const day = new Date(data.createdAt);

  return (
    <Screen
      title={r.title}
      back={false}
      onBack={() => router.replace('/')}
      footer={<Btn label={r.askChat} kind="secondary" onPress={openChat} />}
    >
      <Card style={{ gap: 4 }}>
        <Text style={T.caption}>{r.analyzedOn(`${day.getMonth() + 1}월 ${day.getDate()}일`)}</Text>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <Text style={[T.bodyM, { flex: 1 }]}>{r.summary(summary.prescriptionCount, summary.drugCount)}</Text>
          {sev ? <Chip label={sev} tone={counts.danger ? 'danger' : 'caution'} /> : <Chip label={r.noRisk} tone="success" />}
        </View>
        {summary.hospitals.length > 0 && <Text style={T.caption}>{summary.hospitals.join(' · ')}</Text>}
      </Card>

      <View accessibilityRole="tablist" style={{ flexDirection: 'row', backgroundColor: C.muted, borderRadius: R.control, padding: 4, marginTop: 12 }}>
        {tabs.map(([k, l]) => (
          <Pressable
            key={k}
            accessibilityRole="tab"
            accessibilityState={{ selected: tab === k }}
            onPress={() => setTab(k)}
            style={{ flex: 1, minHeight: 48, justifyContent: 'center', borderRadius: 9, backgroundColor: tab === k ? C.card : 'transparent', alignItems: 'center' }}
          >
            <Text style={{ fontSize: 16, fontWeight: tab === k ? '700' : '500', color: tab === k ? C.p700 : C.text2 }}>{l}</Text>
          </Pressable>
        ))}
      </View>

      {tab === 'safety' && <Safety data={data} onDetail={(id) => router.push({ pathname: '/warning', params: { id: String(id) } })} />}
      {tab === 'med' && <Medication data={data} analysisId={analysisId} onRetried={() => router.replace('/analyzing')} onAsk={openChat} />}
      {tab === 'life' && (
        <Life
          data={data}
          analysisId={analysisId}
          onChange={(life) => setData({ ...data, lifestyle: life })}
          onRetried={() => router.replace('/analyzing')}
        />
      )}
      <Disclaimer />
    </Screen>
  );
}

// 점검에서 빠진 약은 숨기지 않고 맨 위에 보여 줌 (REQ-032)
function Excluded({ data }: { data: AnalysisResult }) {
  if (data.excludedDrugs.length === 0) return null;
  return <Text style={[T.caption, { color: C.warning, marginTop: 12 }]}>{r.excluded(data.excludedDrugs.map((e) => `"${e.rawName}"`).join(', '))}</Text>;
}

function Safety({ data, onDetail }: { data: AnalysisResult; onDetail: (id: number) => void }) {
  if (data.warnings.length === 0) {
    return (
      <View style={{ marginTop: 12 }}>
        <Excluded data={data} />
        <Card tone="success" style={{ marginTop: 12 }}>
          <Text style={T.heading}>{r.noRiskHead}</Text>
          <Text style={[T.body, { marginTop: 6 }]}>{r.noRiskBody(data.summary.drugCount)}</Text>
        </Card>
        <Section title={r.checkedTitle}>
          {data.checkedItems.map((c) => (
            <Card key={c.type} style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <Text style={[T.bodyM, { flex: 1 }]}>{c.label}</Text>
              <Chip label={r.checked} tone="success" />
            </Card>
          ))}
        </Section>
        <Text style={[T.caption, { marginTop: 12 }]}>{r.noRiskNote}</Text>
      </View>
    );
  }
  return (
    <View>
      <Excluded data={data} />
      <View style={{ gap: 12, marginTop: 12 }}>
        {data.warnings.map((w) => (
          <WarningCard key={w.id} w={w} onPress={() => onDetail(w.id)} />
        ))}
      </View>
      <Text style={[T.caption, { marginTop: 12 }]}>{r.judgedNote}</Text>
    </View>
  );
}

function WarningCard({ w, onPress }: { w: Warning; onPress: () => void }) {
  const names = w.drugs.length <= 2 ? w.drugs.map((d) => d.itemName).join(w.type === 'interaction' ? ' + ' : ' · ') : r.drugsCount(w.drugs.length);
  return (
    <Card tone={SEV_TONE[w.severity]} onPress={onPress}>
      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
        <Chip label={r.severity[w.severity]} tone={SEV_TONE[w.severity]} />
        <Text style={[T.label, { flex: 1 }]}>{w.title}</Text>
      </View>
      <Text style={[T.bodyM, { marginTop: 8 }]}>{names || r.noWarningDrugs}</Text>
      <Text style={[T.body, { marginTop: 4 }]}>{w.summary}</Text>
      <Text style={[T.caption, { marginTop: 6 }]}>{r.basis(w.source.name)}</Text>
      <Text style={link}>{r.detail} {'>'}</Text>
    </Card>
  );
}

// 안내문을 만들지 못했을 때 (RG-01-E1에서 안전성만 보고 들어온 경우 포함) — 다시 시도하면 실패한 단계부터 다시 함 (R-3)
function GuideFailed({ analysisId, onRetried }: { analysisId: number; onRetried: () => void }) {
  const [err, setErr] = useState<string | null>(null);
  const retry = async () => {
    try {
      setErr(null);
      await retryAnalysis(analysisId);
      onRetried();
    } catch (e) {
      setErr(errText(e));
    }
  };
  return (
    <Card style={{ marginTop: 12, gap: 8 }}>
      <Text style={T.subhead}>{r.guideFailHead}</Text>
      <Text style={T.body}>{r.guideFailBody}</Text>
      {err && <Text style={[T.caption, { color: C.danger }]}>※ {err}</Text>}
      <Btn label={copy.common.retry} onPress={retry} />
    </Card>
  );
}

const Field = ({ label, value }: { label: string; value: string | null }) => (
  <Text style={T.body}>
    <Text style={T.bodyM}>{label} · </Text>
    {value ?? r.missingField}
  </Text>
);

function Medication({ data, analysisId, onRetried, onAsk }: { data: AnalysisResult; analysisId: number; onRetried: () => void; onAsk: () => void }) {
  if (data.medication.status === 'failed') return <GuideFailed analysisId={analysisId} onRetried={onRetried} />;
  return (
    <View style={{ marginTop: 12, gap: 12 }}>
      <Excluded data={data} />
      {data.medication.items.map((m) => (
        <Card key={m.itemId} style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 8 }}>
            <Text style={[T.subhead, { flex: 1 }]}>{m.itemName}</Text>
            {m.category && <Chip label={m.category} tone="info" />}
          </View>
          <Field label={r.purpose} value={m.purpose} />
          <Field label={r.howTo} value={m.howToTake} />
          <Field label={r.caution} value={m.caution} />
          {m.source && <Text style={T.caption}>{r.source(m.source)}</Text>}
          <Pressable accessibilityRole="button" onPress={onAsk} style={{ minHeight: 48, justifyContent: 'center' }}>
            <Text style={{ color: C.p700, fontWeight: '600', fontSize: 16 }}>{r.askDrug} {'>'}</Text>
          </Pressable>
        </Card>
      ))}
      {data.excludedDrugs.map((e) => (
        <Card key={e.rawName} tone="caution" style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 8 }}>
            <Text style={[T.subhead, { flex: 1 }]}>{e.rawName}</Text>
            <Chip label={r.notFoundChip} tone="danger" />
          </View>
          <Text style={T.body}>{r.notFoundBody}</Text>
        </Card>
      ))}
    </View>
  );
}

const Actions = ({ actions }: { actions: Action[] }) => (
  <>
    {actions.map((a, i) => (
      <Text key={i} style={T.body}>
        · {a.text}
      </Text>
    ))}
  </>
);

function Life({ data, analysisId, onChange, onRetried }: { data: AnalysisResult; analysisId: number; onChange: (l: Lifestyle) => void; onRetried: () => void }) {
  const life = data.lifestyle;
  if (life.status === 'failed') return <GuideFailed analysisId={analysisId} onRetried={onRetried} />;
  const linkCard = life.medicationLinks.length > 0 && (
    <Card style={{ gap: 8 }}>
      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
        <Chip label={r.withDrugs} tone="info" />
        <Text style={[T.label, { flex: 1 }]}>{r.withDrugsTitle}</Text>
      </View>
      {life.medicationLinks.map((l) => (
        <View key={l.itemId} style={{ gap: 2 }}>
          <Text style={T.bodyM}>{l.itemName}</Text>
          <Actions actions={l.actions} />
          {l.requiresClinician && <Chip label={r.clinician} tone="caution" />}
        </View>
      ))}
    </Card>
  );
  if (life.diseases.length === 0) {
    return (
      <View style={{ marginTop: 12, gap: 12 }}>
        <Card tone="caution" style={{ gap: 6 }}>
          <Text style={T.subhead}>{r.noDisease}</Text>
          <Text style={T.body}>{r.noDiseaseBody}</Text>
        </Card>
        {linkCard}
        <DiseasePicker analysisId={analysisId} onChange={onChange} />
      </View>
    );
  }
  const fromUser = life.diseases.every((d) => d.origin === 'user');
  const nameOf = (code: string) => life.diseases.find((d) => d.code === code)?.name ?? code;
  return (
    <View style={{ marginTop: 12, gap: 12 }}>
      <Card style={{ gap: 4 }}>
        <Text style={T.small}>{r.foundDiseases}</Text>
        <Text style={T.subhead}>{life.diseases.map((d) => d.name).join(' · ')}</Text>
        <Text style={T.caption}>{fromUser ? r.diseaseFromUser : `${r.diseaseFrom} (${life.diseases.map((d) => d.code).join(', ')})`}</Text>
      </Card>
      {life.sections.some((s) => s.conflict) &&
        life.sections.filter((s) => s.conflict).map((s, i) => (
          <Card key={i} tone="caution">
            <Chip label={s.conflict!.label} tone="caution" />
            <Text style={[T.body, { marginTop: 6 }]}>{s.conflict!.message}</Text>
          </Card>
        ))}
      {linkCard}
      {life.sections.map((s, i) => (
        <Card key={i} style={{ gap: 6 }}>
          <Text style={T.small}>{nameOf(s.diseaseCode)}</Text>
          <Text style={T.subhead}>{s.title}</Text>
          {s.goal && <Text style={T.bodyM}>{s.goal}</Text>}
          <Actions actions={s.actions} />
        </Card>
      ))}
      {life.warningSigns.some((w) => w.actions.length > 0) && (
        <Card tone="caution" style={{ gap: 6 }}>
          <Text style={T.subhead}>{r.warningSigns}</Text>
          {life.warningSigns.map((w, i) => (
            <Actions key={i} actions={w.actions} />
          ))}
        </Card>
      )}
      {life.sources.length > 0 && (
        <View style={{ gap: 2 }}>
          <Text style={T.small}>{r.sources}</Text>
          {life.sources.map((s) => (
            <Text key={s.id} style={T.caption}>
              · {s.title ? `${s.org} · ${s.title}` : s.org}
            </Text>
          ))}
        </View>
      )}
    </View>
  );
}

// RG-05-E1 질병분류기호가 없을 때 사용자가 직접 질환 고르기 (R-6)
function DiseasePicker({ analysisId, onChange }: { analysisId: number; onChange: (l: Lifestyle) => void }) {
  const [pick, setPick] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const apply = async () => {
    if (!pick) return;
    try {
      setBusy(true);
      setErr(null);
      onChange(await putDiseases(analysisId, pick === 'none' ? [] : [pick]));
    } catch (e) {
      setErr(errText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <Text style={T.label}>{r.pickDisease}</Text>
      {PICKABLE_DISEASES.map((d) => (
        <Radio key={d.code} on={pick === d.code} label={d.name} onPress={() => setPick(d.code)} />
      ))}
      <Radio on={pick === 'none'} label={r.pickNone} onPress={() => setPick('none')} />
      {err && <Text style={[T.caption, { color: C.danger }]}>※ {err}</Text>}
      <Btn label={r.pickApply} disabled={!pick || pick === 'none' || busy} onPress={apply} style={{ marginTop: 8 }} />
    </Card>
  );
}
