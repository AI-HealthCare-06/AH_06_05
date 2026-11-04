import { useRouter } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, Text, TextInput, View } from 'react-native';

import { useChatLauncher } from '@/features/chatbot/launcher';
import { getMe } from '@/features/common/api';
import { useFlow } from '@/features/ocr/flow';
import { PICKABLE_DISEASES } from '@/features/rag/diseases';
import { getAnalysis, putDiseases, retryAnalysis, sendGuideFeedback } from '@/features/rag/api';
import type { Action, AnalysisResult, GuideFeedback, Severity, Warning } from '@/features/rag/types';
import { ApiError } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { drugLabel } from '@/shared/drugName';
import { C, R, T } from '@/shared/theme';
import { DocIcon } from '@/shared/ui/icons';
import { Btn, Bullet, Card, Check, Chip, Disclaimer, Radio, Screen, Section } from '@/shared/ui';

const r = copy.result;
type TabKey = 'safety' | 'med' | 'life';
type Lifestyle = AnalysisResult['lifestyle'];
const SEV_TONE: Record<Severity, 'danger' | 'caution' | 'info'> = { danger: 'danger', caution: 'caution', info: 'info' };
const link = { color: C.p700, fontWeight: '600' as const, marginTop: 8, fontSize: 16 };
const errText = (e: unknown) => (e instanceof ApiError ? e.message : copy.common.serverError);

// RG-02 · RG-02-E1 안전성 / RG-04 복약 안내 / RG-05 · RG-05-E1 생활습관 (R-4 한 번에 받아서 탭만 바꿈)
export default function Result() {
  const router = useRouter();
  const goHome = () => router.replace('/'); // 결과 화면은 쌓인 화면이 분석 중이라 홈으로 보냄 (뒤로 스와이프는 꺼 둠)
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
      <Screen title={r.title} onBack={goHome} footer={<Btn label={copy.common.goHome} onPress={goHome} />}>
        <Text style={T.body}>{r.loadFail}</Text>
      </Screen>
    );
  }
  if (!data) {
    return (
      <Screen
        title={r.title}
        onBack={goHome}
        footer={error ? <Btn label={copy.common.retry} onPress={load} /> : undefined}
      >
        {error ? <Text style={[T.body, { color: C.danger }]}>{r.loadFail} ({error})</Text> : <ActivityIndicator color={C.p600} style={{ marginTop: 40 }} />}
      </Screen>
    );
  }

  const { summary } = data;
  const counts = summary.warningCounts;
  const sev = [counts.danger && `${r.severity.danger} ${counts.danger}`, counts.caution && `${r.severity.caution} ${counts.caution}`, counts.info && `${r.severity.info} ${counts.info}`].filter(Boolean).join(', ');
  const tabs: [TabKey, string][] = [['safety', r.tabs.safety], ['med', r.tabs.med], ['life', r.tabs.life]];
  const day = new Date(data.createdAt);

  return (
    <Screen
      title={r.title}
      onBack={goHome}
      footer={<Btn label={r.askChat} kind="secondary" onPress={() => openChat({ from: 'RG-02', analysisId })} />}
    >
      <Card style={{ gap: 4 }}>
        <Text style={T.caption}>{r.analyzedOn(`${day.getMonth() + 1}월 ${day.getDate()}일`)}</Text>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <Text style={[T.bodyM, { flex: 1 }]}>{r.summary(summary.prescriptionCount, summary.drugCount)}</Text>
          {sev ? <Chip label={sev} tone={counts.danger ? 'danger' : 'caution'} /> : <Chip label={r.noRisk} tone="success" />}
        </View>
        {summary.hospitals.length > 0 && <Text style={T.caption}>{summary.hospitals.join(', ')}</Text>}
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
      {tab === 'med' && <Medication data={data} analysisId={analysisId} onRetried={() => router.replace('/analyzing')} onAsk={(itemId) => openChat({ from: 'RG-04', analysisId, context: { type: 'drug', id: itemId } })} />}
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
  const names = (list: typeof data.excludedDrugs) => list.map((e) => `"${e.rawName}"`).join(', ');
  const notOral = data.excludedDrugs.filter((e) => e.reason === 'not_oral');
  const missing = data.excludedDrugs.filter((e) => e.reason !== 'not_oral');
  return (
    <>
      {missing.length > 0 && <Text style={[T.caption, { color: C.warning, marginTop: 12 }]}>{r.excluded(names(missing))}</Text>}
      {notOral.length > 0 && <Text style={[T.caption, { color: C.warning, marginTop: 12 }]}>{r.notOral(names(notOral))}</Text>}
    </>
  );
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
  const names = w.drugs.length <= 2 ? w.drugs.map((d) => drugLabel(d.itemName)).join(w.type === 'interaction' ? ' + ' : ', ') : r.drugsCount(w.drugs.length);
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
    <Text style={T.bodyM}>{label}: </Text>
    {value ?? r.missingField}
  </Text>
);

function Medication({ data, analysisId, onRetried, onAsk }: { data: AnalysisResult; analysisId: number; onRetried: () => void; onAsk: (itemId: number) => void }) {
  if (data.medication.status === 'failed') return <GuideFailed analysisId={analysisId} onRetried={onRetried} />;
  return (
    <View style={{ marginTop: 12, gap: 12 }}>
      <Excluded data={data} />
      {data.medication.items.map((m) => (
        <Card key={m.itemId} style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 8 }}>
            <Text style={[T.subhead, { flex: 1 }]}>{drugLabel(m.itemName)}</Text>
            {m.category && <Chip label={m.category} tone="info" />}
          </View>
          <Field label={r.purpose} value={m.purpose} />
          <Field label={r.howTo} value={m.howToTake?.split(' · ').join(', ') ?? null} />
          {m.cautions?.length ? (
            <View style={{ gap: 2 }}>
              <Text style={T.bodyM}>{r.caution}</Text>
              {m.cautions.map((c) => (
                <Bullet key={c} text={c} />
              ))}
              <Text style={T.small}>{r.cautionsFoot}</Text>
            </View>
          ) : (
            <Field label={r.caution} value={m.caution} />
          )}
          {m.source && <Text style={T.caption}>{r.source(m.source)}</Text>}
          <Pressable accessibilityRole="button" onPress={() => onAsk(m.itemId)} style={{ minHeight: 48, justifyContent: 'center' }}>
            <Text style={{ color: C.p700, fontWeight: '600', fontSize: 16 }}>{r.askDrug} {'>'}</Text>
          </Pressable>
        </Card>
      ))}
      {data.excludedDrugs.map((e) => (
        <Card key={e.rawName} tone="caution" style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 8 }}>
            <Text style={[T.subhead, { flex: 1 }]}>{e.rawName}</Text>
            <Chip label={e.reason === 'not_oral' ? r.notOralChip : r.notFoundChip} tone={e.reason === 'not_oral' ? 'neutral' : 'danger'} />
          </View>
          <Text style={T.body}>{e.reason === 'not_oral' ? r.notOralBody : r.notFoundBody}</Text>
        </Card>
      ))}
      {data.medication.guideId > 0 && <GuideFeedbackBox guideId={data.medication.guideId} saved={data.medication.feedback ?? null} />}
    </View>
  );
}

// RG-04 안내문 피드백 (R-9). 같은 처방전으로는 한 번만 보낼 수 있음. 보내면 잠그고, 다시 열어도 서버가 준 feedback으로 잠근 채 보여 줌 (이미 보냈으면 서버가 409 FEEDBACK_ALREADY_SENT)
function GuideFeedbackBox({ guideId, saved }: { guideId: number; saved: GuideFeedback | null }) {
  const [rating, setRating] = useState<1 | -1 | null>(saved?.rating ?? null);
  const [comment, setComment] = useState(saved?.comment ?? '');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(saved !== null); // 서버가 "이미 보냈음"을 알려 주면 다시 열어도 막힌 채로 보여 줌
  const [err, setErr] = useState<string | null>(null);
  const sending = useRef(false); // 빠르게 두 번 눌러도 한 번만 보냄
  const send = async () => {
    if (rating === null || sending.current || sent) return;
    sending.current = true;
    try {
      setBusy(true);
      setErr(null);
      await sendGuideFeedback(guideId, rating, comment.trim() || undefined);
      setSent(true); // 보낸 뒤에는 고르기 · 입력 · 보내기를 모두 막고 "의견을 보냈어요."를 계속 보여 줌
    } catch (e) {
      if (e instanceof ApiError && e.code === 'FEEDBACK_ALREADY_SENT') setSent(true); // 다른 화면에서 이미 보낸 경우: 서버가 거절하면 막힌 상태로 바꿈
      else setErr(errText(e));
    } finally {
      sending.current = false;
      setBusy(false);
    }
  };
  return (
    <Card style={{ gap: 4 }}>
      <Text style={T.label}>{r.feedbackTitle}</Text>
      <Radio on={rating === 1} label={r.feedbackYes} onPress={() => setRating(1)} disabled={sent} />
      <Radio on={rating === -1} label={r.feedbackNo} onPress={() => setRating(-1)} disabled={sent} />
      <TextInput
        accessibilityLabel={r.feedbackComment}
        placeholder={r.feedbackComment}
        placeholderTextColor={C.text3}
        value={comment}
        onChangeText={setComment}
        maxLength={500}
        multiline
        editable={!sent}
        style={{ minHeight: 64, borderWidth: 1, borderColor: C.border, borderRadius: R.control, padding: 12, fontSize: 16, color: C.text, opacity: sent ? 0.5 : 1 }}
      />
      {err && <Text style={[T.caption, { color: C.danger }]}>※ {err}</Text>}
      <Btn label={sent ? r.feedbackSent : r.feedbackSend} disabled={sent || rating === null || busy} onPress={send} style={{ marginTop: 8 }} />
      {sent && (
        <Text style={[T.caption, { color: C.success, textAlign: 'center', marginTop: 8 }]} accessibilityLiveRegion="polite">
          {r.feedbackThanks}
        </Text>
      )}
    </Card>
  );
}

const Actions = ({ actions }: { actions: Action[] }) => (
  <>
    {actions.map((a, i) => (
      <Bullet key={i} text={a.text} />
    ))}
  </>
);

function Life({ data, analysisId, onChange, onRetried }: { data: AnalysisResult; analysisId: number; onChange: (l: Lifestyle) => void; onRetried: () => void }) {
  const router = useRouter();
  const [editInitial, setEditInitial] = useState<string[] | null>(null); // 질환 추가 중이면 미리 체크해 둘 질환 코드 (RG-05-E1 미리 채움)
  const editing = editInitial !== null;
  const life = data.lifestyle;
  if (life.status === 'failed') return <GuideFailed analysisId={analysisId} onRetried={onRetried} />;
  const linkCard = life.medicationLinks.length > 0 && (
    <Card style={{ gap: 8 }}>
      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
        <Chip label={r.withDrugs} tone="info" />
        <Text style={[T.label, { flex: 1 }]}>{r.withDrugsTitle}</Text>
      </View>
      {life.medicationLinks.map((l, i) => (
        <View key={`${l.itemId}-${i}`} style={{ gap: 2 }}>
          <Text style={T.bodyM}>{drugLabel(l.itemName)}</Text>
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
  // 분석 질환은 처방전 질환과 내 정보 질환을 합쳐 씀 (#101)
  const rxCodes = life.diseases.filter((d) => d.origin === 'prescription').map((d) => d.code);
  const hasProfile = life.diseases.some((d) => d.origin === 'profile');
  const fromText = fromUser
    ? r.diseaseFromUser
    : rxCodes.length === 0
      ? r.diseaseFromProfile
      : `${hasProfile ? r.diseaseFromBoth : r.diseaseFrom} (${rxCodes.join(', ')})`;
  // 질환 추가: 확인한 질환과 지금 내 정보의 질환을 미리 체크해 둠. 내 정보를 못 불러오면 확인한 질환만
  const startEdit = async () => {
    const fromAnalysis = PICKABLE_DISEASES.filter((p) => life.diseases.some((d) => d.name === p.name)).map((p) => p.code);
    let fromProfile: string[] = [];
    try {
      const me = await getMe();
      fromProfile = PICKABLE_DISEASES.filter((p) => (me.health.diseases as string[]).includes(p.id)).map((p) => p.code);
    } catch {
      // 확인한 질환만 미리 체크
    }
    setEditInitial([...new Set([...fromAnalysis, ...fromProfile])]);
  };
  const nameOf = (code: string) => life.diseases.find((d) => d.code === code)?.name ?? code;
  return (
    <View style={{ marginTop: 12, gap: 12 }}>
      <Card style={{ gap: 4 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text style={T.small}>{r.foundDiseases}</Text>
          {!editing && (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={r.editDisease}
              hitSlop={10}
              onPress={startEdit}
              style={{ backgroundColor: C.p50, borderRadius: R.chip, paddingHorizontal: 10, paddingVertical: 4 }}
            >
              <Text style={{ fontSize: 13, fontWeight: '700', color: C.p700 }}>{r.editDisease}</Text>
            </Pressable>
          )}
        </View>
        <Text style={T.subhead}>{life.diseases.map((d) => d.name).join(', ')}</Text>
        <Text style={T.caption}>{fromText}</Text>
      </Card>
      {editInitial !== null && (
        <DiseasePicker
          analysisId={analysisId}
          editing
          initial={editInitial}
          onChange={(l) => {
            setEditInitial(null);
            onChange(l);
          }}
          onCancel={() => setEditInitial(null)}
        />
      )}
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
      <Btn label={copy.challenge.start} onPress={() => router.push('/challenge-select')} />
      {life.sources.length > 0 && (
        <View style={{ backgroundColor: C.card, borderRadius: R.card, borderWidth: 1, borderColor: C.border, padding: 16 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <DocIcon />
            <Text style={T.small} accessibilityRole="header">
              {r.sourceTitle}
            </Text>
          </View>
          {life.sources.map((s) => (
            <View key={s.id} style={{ marginTop: 12 }}>
              <Text style={{ fontSize: 15, fontWeight: '600', color: C.text }}>{s.org}</Text>
              {s.title ? <Text style={[T.caption, { marginTop: 2 }]}>{s.title}</Text> : null}
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

// RG-05-E1 질병분류기호가 없을 때 사용자가 직접 질환 고르기 (R-6)
// editing이면 확인한 질환에 체크를 미리 해 두고 더하거나 뺌 (이 분석에만 적용, 내 정보는 그대로)
function DiseasePicker({
  analysisId,
  onChange,
  initial = [],
  editing = false,
  onCancel,
}: {
  analysisId: number;
  onChange: (l: Lifestyle) => void;
  initial?: string[];
  editing?: boolean;
  onCancel?: () => void;
}) {
  const [picks, setPicks] = useState<string[]>(initial); // 여러 질환을 고를 수 있음 (서버 R-6은 질환 코드 목록을 받음)
  const [none, setNone] = useState(false); // "해당 없음"은 다른 선택과 같이 고를 수 없음
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const canApply = picks.length > 0 || editing; // 추가 화면에서는 체크를 모두 풀어 질환을 모두 뺄 수도 있음
  const apply = async () => {
    if (!canApply) return;
    try {
      setBusy(true);
      setErr(null);
      onChange(await putDiseases(analysisId, picks));
    } catch (e) {
      setErr(errText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <Text style={T.label}>{r.pickDisease}</Text>
      {editing && <Text style={T.caption}>{r.editDiseaseNote}</Text>}
      {PICKABLE_DISEASES.map((d) => (
        <Check
          key={d.code}
          on={picks.includes(d.code)}
          label={d.name}
          onPress={() => {
            setNone(false);
            setPicks((cur) => (cur.includes(d.code) ? cur.filter((c) => c !== d.code) : [...cur, d.code]));
          }}
        />
      ))}
      {!editing && (
        <Check
          on={none}
          label={r.pickNone}
          onPress={() => {
            setNone(!none);
            setPicks([]);
          }}
        />
      )}
      {err && <Text style={[T.caption, { color: C.danger }]}>※ {err}</Text>}
      <Btn label={r.pickApply} disabled={!canApply || busy} onPress={apply} style={{ marginTop: 8 }} />
      {editing && <Btn label={r.editDiseaseCancel} kind="secondary" disabled={busy} onPress={() => onCancel?.()} />}
    </Card>
  );
}
