// CB-01 화면 부품 (설계 메모 4-2 ~ 4-8 항목). 문구는 copy.chatbot (설계 메모 6장)
import { useCallback, useEffect, useState } from 'react';
import { Linking, Platform, Pressable, Text, TextInput, View } from 'react-native';

import { getAnalysis } from '@/features/rag/api';
import type { AnalysisResult } from '@/features/rag/types';
import { copy } from '@/shared/copy';
import { C, L, R, T } from '@/shared/theme';
import { Btn, Card, Chip } from '@/shared/ui';

import { analyzedAt } from './time';
import type { ErrorKind } from './useChat';
import type { AnswerType, ChatContext, Message, SafetyInfo } from './types';

const c = copy.chatbot;
const MAX_LENGTH = 500; // 명세서 H-3

// 답변 라벨 색 (설계 메모 3-1 항목)
const LABEL_TONE: Record<Exclude<AnswerType, 'normal'>, 'info' | 'neutral' | 'caution' | 'danger'> = {
  clarify: 'info',
  partial: 'neutral',
  no_evidence: 'neutral',
  refer: 'caution',
  emergency: 'danger',
  crisis: 'info',
};

const open = (url: string) => Linking.openURL(url).catch(() => undefined);

export function UserBubble({ text, faded }: { text: string; faded?: boolean }) {
  return (
    <View style={{ alignSelf: 'flex-end', maxWidth: '85%', backgroundColor: faded ? C.muted : C.p600, borderRadius: R.card, padding: 12 }}>
      <Text style={[T.body, { color: faded ? C.text3 : C.onPrimary }]}>{text}</Text>
    </View>
  );
}

export function Generating() {
  return (
    <View style={{ alignSelf: 'flex-start' }} accessibilityLiveRegion="polite">
      <Text style={T.caption}>{c.generating}</Text>
    </View>
  );
}

export function AnswerBubble({ m }: { m: Message }) {
  const type = m.answerType ?? 'normal';
  return (
    <Card style={{ alignSelf: 'flex-start', maxWidth: '92%', gap: 8 }}>
      {type !== 'normal' && <Chip label={c.labels[type]} tone={LABEL_TONE[type]} />}
      <Text style={T.body}>{m.content}</Text>
      {m.sources?.map((s) => (
        <Text key={s.title} style={T.caption}>
          {c.source(s.title)}
        </Text>
      ))}
    </Card>
  );
}

// 가까운 응급실: 카카오맵 앱으로 열고, 안 되면 모바일 웹 (설계 메모 4-6 항목, 위치 권한 없음)
function findER() {
  const q = encodeURIComponent('응급실');
  const web = `https://m.map.kakao.com/scheme/search?q=${q}`;
  if (Platform.OS === 'web') return void open(web);
  Linking.openURL(`kakaomap://search?q=${q}`).catch(() => open(web));
}

// 테두리만 있는 보조 버튼 (E4 응급실 찾기, E5 119)
function OutlineBtn({ label, color, onPress }: { label: string; color: string; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => ({ minHeight: L.button, borderRadius: R.control, borderWidth: 1.5, borderColor: color, alignItems: 'center', justifyContent: 'center', opacity: pressed ? 0.8 : 1 })}
    >
      <Text style={{ fontSize: 17, fontWeight: '700', color }}>{label}</Text>
    </Pressable>
  );
}

// E4 긴급 안내, E5 도움 연결. 동시 해당이면 E4 아래에 109만 (설계 메모 4-6 항목)
export function SafetyCards({
  safety,
  onNoSymptom,
  relieved,
}: {
  safety: SafetyInfo;
  onNoSymptom?: () => void; // 없으면 칩을 끔 (원문이 없어 다시 보낼 수 없음)
  relieved: boolean;
}) {
  const emergency = safety.types.includes('emergency');
  const crisis = safety.types.includes('crisis');
  const showChip = emergency && !crisis && !safety.overdose; // 과다 복용, 2층 응급, 동시 해당은 칩 없음
  return (
    <View style={{ gap: 10, alignSelf: 'stretch' }}>
      {emergency && (
        <Card tone="danger" style={{ gap: 10 }}>
          <Chip label={c.labels.emergency} tone="danger" />
          <Text style={T.bodyM}>{c.emergency[0]}</Text>
          <Btn label={c.call119} kind="danger" onPress={() => open('tel:119')} />
          <OutlineBtn label={c.findER} color={C.danger} onPress={findER} />
          <Text style={T.caption}>{c.emergency[1]}</Text>
          {showChip && (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ disabled: !onNoSymptom || relieved }}
              onPress={onNoSymptom && !relieved ? onNoSymptom : undefined}
              style={{ minHeight: L.touch, borderRadius: R.chip, borderWidth: 1, borderColor: C.borderStrong, paddingHorizontal: 16, alignSelf: 'flex-start', justifyContent: 'center', opacity: onNoSymptom && !relieved ? 1 : 0.5 }}
            >
              <Text style={[T.label, { color: C.text2 }]}>{c.noSymptom}</Text>
            </Pressable>
          )}
        </Card>
      )}
      {crisis && (
        <Card tone="info" style={{ gap: 10 }}>
          {!emergency && <Chip label={c.labels.crisis} tone="info" />}
          <Text style={T.body}>{c.crisis[0]}</Text>
          <Btn label={c.call109} onPress={() => open('tel:109')} />
          {!emergency && <OutlineBtn label={c.danger119} color={C.p700} onPress={() => open('tel:119')} />}
          {!emergency && <Text style={T.caption}>{c.crisis[1]}</Text>}
        </Card>
      )}
      {relieved && (
        <Card style={{ alignSelf: 'flex-start', maxWidth: '92%' }}>
          <Text style={T.body}>{c.noSymptomReply}</Text>
        </Card>
      )}
    </View>
  );
}

// E6 답변 오류 (설계 메모 4-7 항목). 403은 서버 문구를 보이고 [다시 시도]를 숨김
export function ErrorCard({ kind, onRetry }: { kind: ErrorKind; onRetry: () => void }) {
  const lines = typeof kind === 'object' ? [kind.message] : kind === 'tooMany' ? c.errorTooMany : c.error;
  return (
    <Card style={{ alignSelf: 'stretch', gap: 8 }}>
      <Chip label={c.labels.error} />
      {lines.map((l) => (
        <Text key={l} style={T.body}>
          {l}
        </Text>
      ))}
      {typeof kind !== 'object' && <Btn label={copy.common.retry} kind="secondary" onPress={onRetry} />}
    </Card>
  );
}

// E6 다시 시도가 뒤에 다른 대화가 있을 때 성공함: 오류 카드 자리와 맨 아래 답 위 인용 (설계 메모 4-7 항목)
export function ResentCard() {
  return (
    <Card style={{ alignSelf: 'stretch' }}>
      <Text style={T.caption}>{c.resent}</Text>
    </Card>
  );
}

export function QuoteLine({ text }: { text: string }) {
  return (
    <Text style={[T.caption, { alignSelf: 'flex-start' }]} numberOfLines={2}>
      {c.quoted(text)}
    </Text>
  );
}

// 맥락 카드에 쓰는 분석 요약 (R-4에서 꺼냄, 설계 메모 3-3 AnalysisSummary)
function targetLabel(a: AnalysisResult, ctx?: ChatContext) {
  if (!ctx) return null;
  if (ctx.type === 'warning') {
    const w = a.warnings.find((x) => x.id === ctx.id);
    return w ? c.contextWarning(w.drugs.map((d) => d.itemName).join(' + ')) : null;
  }
  const d = a.medication.items.find((x) => x.itemId === ctx.id);
  return d ? c.contextDrug(d.itemName) : null;
}

export function ContextCard({ analysisId, context }: { analysisId: number; context?: ChatContext }) {
  const [a, setA] = useState<AnalysisResult | null>(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => {
    setFailed(false);
    getAnalysis(analysisId).then(setA, () => setFailed(true));
  }, [analysisId]);
  useEffect(load, [load]);
  if (failed) {
    return (
      <Card tone="info" style={{ gap: 6, alignSelf: 'stretch' }}>
        <Text style={T.body}>{c.contextFail}</Text>
        <Btn label={c.reload} kind="ghost" onPress={load} />
      </Card>
    );
  }
  if (!a) return null;
  const when = analyzedAt(a.createdAt);
  const counts = a.summary.warningCounts;
  const target = targetLabel(a, context);
  return (
    <Card tone="info" style={{ gap: 4, alignSelf: 'stretch' }}>
      <Text style={T.bodyM}>{c.contextTitle}</Text>
      <Text style={T.caption}>
        {c.contextSummary(when.label, when.daysAgo, a.summary.drugCount, counts.danger + counts.caution + counts.info)}
      </Text>
      {target && <Text style={T.caption}>{target}</Text>}
    </Card>
  );
}

export function SuggestChips({ items, onPick, disabled }: { items: readonly string[]; onPick: (q: string) => void; disabled?: boolean }) {
  return (
    <View style={{ gap: 8 }}>
      {items.map((q) => (
        <Pressable
          key={q}
          accessibilityRole="button"
          accessibilityState={{ disabled: !!disabled }}
          onPress={disabled ? undefined : () => onPick(q)}
          style={{ minHeight: L.touch, borderRadius: R.control, borderWidth: 1, borderColor: C.p100, backgroundColor: C.card, paddingHorizontal: 14, justifyContent: 'center' }}
        >
          <Text style={[T.body, { color: disabled ? C.text3 : C.p700 }]}>{q}</Text>
        </Pressable>
      ))}
    </View>
  );
}

// 답 아래 꼬리질문: 이 대화에서 아직 묻지 않은 것 2개 (약 중단, 변경 질문은 두지 않음, 설계 메모 4-4 항목)
export function FollowUps({ asked, onPick, disabled }: { asked: Set<string>; onPick: (q: string) => void; disabled?: boolean }) {
  const items = c.followChips.filter((q) => !asked.has(q)).slice(0, 2);
  if (!items.length) return null;
  return (
    <View style={{ gap: 8 }}>
      <Text style={T.caption}>{c.followTitle}</Text>
      <SuggestChips items={items} onPick={onPick} disabled={disabled} />
    </View>
  );
}

// E1 첫 대화 (설계 메모 4-2 항목). 기록 여부를 모르면 "오늘은 어떤 게 궁금하세요?"
export function Empty({ hasHistory, onPick, disabled }: { hasHistory: boolean | null; onPick: (q: string) => void; disabled?: boolean }) {
  return (
    <View style={{ gap: 12 }}>
      <Text style={T.title}>{c.emptyTitle}</Text>
      <Text style={T.body}>{c.emptyBody}</Text>
      <Card style={{ gap: 10 }}>
        <Text style={T.subhead}>{hasHistory === false ? c.emptyNoHistory : c.emptyHasHistory}</Text>
        <Text style={T.caption}>{c.startWith}</Text>
        <SuggestChips items={c.recommended} onPick={onPick} disabled={disabled} />
      </Card>
      <Text style={[T.caption, { textAlign: 'center' }]}>{c.notice}</Text>
    </View>
  );
}

// 입력창 (설계 메모 4-8 항목): 여러 줄, 500자, 보낼 글자가 있고 답을 기다리지 않을 때만 보냄. 첨부, 받아쓰기는 뒤에
export function Composer({ onSend, busy }: { onSend: (text: string) => void; busy: boolean }) {
  const [text, setText] = useState('');
  const ready = text.trim().length > 0 && !busy;
  const send = () => {
    if (!ready) return;
    onSend(text.trim());
    setText('');
  };
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
      <TextInput
        value={text}
        onChangeText={setText}
        placeholder={c.placeholder}
        placeholderTextColor={C.text3}
        multiline
        maxLength={MAX_LENGTH}
        style={{ flex: 1, minHeight: L.touch, maxHeight: 140, borderWidth: 1, borderColor: C.border, borderRadius: R.control, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, color: C.text, backgroundColor: C.card }}
      />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={c.send}
        accessibilityState={{ disabled: !ready }}
        onPress={send}
        style={{ width: L.touch, height: L.touch, borderRadius: L.touch / 2, backgroundColor: ready ? C.p600 : C.muted, alignItems: 'center', justifyContent: 'center' }}
      >
        <Text style={{ fontSize: 20, fontWeight: '700', color: ready ? C.onPrimary : C.text3 }}>↑</Text>
      </Pressable>
    </View>
  );
}

// 안전 모드: 입력창 바로 위 작은 한 줄, 닫을 수 없음 (설계 메모 4-6 항목)
export function SafetyLine() {
  return (
    <Pressable accessibilityRole="link" onPress={() => open('tel:109')} style={{ minHeight: L.touch, justifyContent: 'center' }}>
      <Text style={[T.caption, { color: C.info }]}>{c.safetyLine}</Text>
    </Pressable>
  );
}
