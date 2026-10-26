// CB-01 화면 부품 (설계 메모 4-2 ~ 4-8 항목). 문구는 copy.chatbot (설계 메모 6장)
import { useCallback, useEffect, useRef, useState } from 'react';
import { Linking, Modal, Platform, Pressable, Text, TextInput, View, type NativeSyntheticEvent, type TextInputKeyPressEventData } from 'react-native';

import { getAnalysis } from '@/features/rag/api';
import type { AnalysisResult } from '@/features/rag/types';
import { copy } from '@/shared/copy';
import { C, L, R, T } from '@/shared/theme';
import { dictationSeen, setDictationSeen } from '@/shared/storage/chat';
import { Btn, Card, Chip } from '@/shared/ui';
import { MicIcon } from '@/shared/ui/icons';

import { analyzedAt } from './time';
import type { ErrorKind } from './useChat';
import type { AnswerType, ChatContext, Message, SafetyInfo } from './types';

const c = copy.chatbot;
const MAX_LENGTH = 500; // 명세서 H-3
const REVEAL_MS = 1500; // 새 답은 길이와 상관없이 이 시간 안에 다 보임 (시작값, 10/26 수인 결정)
const REVEAL_STEP_MS = 30;
const DICTATION_TIPS = 3; // 받아쓰기 안내는 처음 3번까지 (설계 메모 4-10 항목)
const INPUT_MAX = 140; // 입력창 높이 48 ~ 140, 넘으면 안에서 스크롤 (설계 메모 4-8 항목)
const isWeb = Platform.OS === 'web';

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

// 피드백을 붙이는 답: 실제 답만 (재질문, 긴급, 자해, 오류에는 없음, 설계 메모 4-3 항목)
const FEEDBACK_ON: AnswerType[] = ['normal', 'partial', 'no_evidence', 'refer'];

// 답은 서버가 검사를 마친 뒤 한 번에 받고, 화면만 글자를 차례로 보여 줌 (와이어프레임 CB-01, 설계 메모 4-3 항목)
// 화면 읽기에는 처음부터 전체 글. 다 보인 뒤에 출처와 피드백
function useReveal(full: string, on: boolean) {
  const [n, setN] = useState(on ? 0 : full.length);
  useEffect(() => {
    if (n >= full.length) return;
    const step = Math.max(1, Math.ceil(full.length / (REVEAL_MS / REVEAL_STEP_MS)));
    const t = setTimeout(() => setN((x) => Math.min(full.length, x + step)), REVEAL_STEP_MS);
    return () => clearTimeout(t);
  }, [n, full]);
  return { text: full.slice(0, n), done: n >= full.length };
}

export function AnswerBubble({ m, reveal = false }: { m: Message; reveal?: boolean }) {
  const type = m.answerType ?? 'normal';
  const shown = useReveal(m.content, reveal);
  return (
    <Card style={{ alignSelf: 'flex-start', maxWidth: '92%', gap: 8 }}>
      {type !== 'normal' && <Chip label={c.labels[type]} tone={LABEL_TONE[type]} />}
      <Text style={T.body} accessibilityLabel={m.content}>
        {shown.text}
      </Text>
      {shown.done && m.sources?.map((s) => (
        <Text key={s.title} style={T.caption}>
          {c.source(s.title)}
        </Text>
      ))}
      {shown.done && FEEDBACK_ON.includes(type) && <Feedback />}
    </Card>
  );
}

function Pill({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: on }}
      onPress={onPress}
      style={{ minHeight: L.touch, paddingHorizontal: 12, borderRadius: R.chip, borderWidth: 1, borderColor: on ? C.p600 : C.border, backgroundColor: on ? C.p50 : C.card, justifyContent: 'center' }}
    >
      <Text style={[T.label, { fontSize: 14, color: on ? C.p700 : C.text2 }]}>{label}</Text>
    </Pressable>
  );
}

// [도움 됐어요] [답변이 이상해요]: 누르면 바로 바뀌고, 같은 것을 다시 누르면 취소, 반대쪽을 누르면 바뀜 (설계 메모 4-3 항목)
// "이상해요"는 이유 창을 띄우고 이유를 안 골라도 닫을 수 있음. 피드백 API가 없어 이 창에서만 기억함
type Choice = { kind: 'good' } | { kind: 'bad'; reason?: string } | null;

function Feedback() {
  const [choice, setChoice] = useState<Choice>(null);
  const [asking, setAsking] = useState(false);
  const [thanks, setThanks] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);
  const thank = () => {
    setThanks(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setThanks(false), 2000);
  };
  const pickGood = () => {
    if (choice?.kind === 'good') return setChoice(null);
    setChoice({ kind: 'good' }); // "이상해요"에서 바꾸면 골랐던 이유는 지움
    thank();
  };
  const pickBad = () => {
    if (choice?.kind === 'bad') return setChoice(null);
    setChoice({ kind: 'bad' });
    setAsking(true);
  };
  const close = (reason?: string) => {
    setAsking(false);
    if (reason) setChoice({ kind: 'bad', reason });
    thank();
  };
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
      <Pill label={c.feedbackGood} on={choice?.kind === 'good'} onPress={pickGood} />
      <Pill label={c.feedbackBad} on={choice?.kind === 'bad'} onPress={pickBad} />
      {thanks && (
        <Text style={T.caption} accessibilityLiveRegion="polite">
          {c.feedbackThanks}
        </Text>
      )}
      <Modal visible={asking} transparent animationType="slide" onRequestClose={() => close()}>
        <Pressable style={{ flex: 1, backgroundColor: C.dim, justifyContent: 'flex-end' }} onPress={() => close()}>
          <Pressable style={{ backgroundColor: C.card, borderTopLeftRadius: R.card, borderTopRightRadius: R.card, padding: 20, gap: 10 }} accessibilityViewIsModal>
            {c.feedbackReasons.map((r) => (
              <Btn key={r} label={r} kind="secondary" onPress={() => close(r)} />
            ))}
            <Btn label={c.feedbackClose} kind="ghost" onPress={() => close()} />
          </Pressable>
        </Pressable>
      </Modal>
    </View>
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

// 입력창 (설계 메모 4-8, 4-10 항목): 여러 줄, 500자, 보낼 글자가 있고 답을 기다리지 않을 때만 보냄. 첨부는 2단계
// 보낼 글자가 없으면 전송 자리에 🎤: 누르면 입력칸에 포커스가 가서 키보드가 올라옴 (키보드 마이크를 앱이 대신 누를 수는 없음)
export function Composer({ onSend, busy }: { onSend: (text: string) => void; busy: boolean }) {
  const [text, setText] = useState('');
  const [tip, setTip] = useState(false);
  const [height, setHeight] = useState<number>(L.touch); // 웹 입력칸 높이 (아래 measure)
  const seen = useRef<number | null>(null);
  const input = useRef<TextInput>(null);
  // 입력칸을 떠나면 안내를 닫는 타이머. 🎤를 다시 누르면 웹은 누르는 순간 포커스가 빠지므로 dictate에서 취소함 (#127 채연 리뷰)
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => void (blurTimer.current && clearTimeout(blurTimer.current)), []);
  useEffect(() => {
    void dictationSeen().then((n) => (seen.current = n));
  }, []);
  const hasText = text.trim().length > 0;
  const ready = hasText && !busy;
  const send = () => {
    if (!ready) return;
    onSend(text.trim());
    setText('');
    setHeight(L.touch);
  };
  // 웹: Enter = 보내기, Shift+Enter = 줄바꿈, 한글 조합 중 Enter는 보내지 않음 (마지막 글자 중복 방지). 앱은 Enter = 줄바꿈
  const key = (e: NativeSyntheticEvent<TextInputKeyPressEventData>) => {
    if (!isWeb || e.nativeEvent.key !== 'Enter') return;
    const k = e.nativeEvent as unknown as KeyboardEvent; // react-native-web은 DOM KeyboardEvent를 그대로 넘김
    if (k.shiftKey || k.isComposing || k.keyCode === 229) return;
    e.preventDefault();
    send();
  };
  const dictate = () => {
    if (blurTimer.current) clearTimeout(blurTimer.current);
    input.current?.focus();
    const n = seen.current ?? 0;
    if (n >= DICTATION_TIPS) return setTip(false); // 3번이 지나면 안내 없이 키보드만 (설계 메모 4-10)
    seen.current = n + 1;
    void setDictationSeen(n + 1);
    setTip(true);
  };
  const never = () => {
    seen.current = DICTATION_TIPS;
    void setDictationSeen(DICTATION_TIPS);
    setTip(false);
  };
  // 웹은 textarea가 저절로 커지거나 줄지 않아, 글이 바뀔 때마다 높이를 잠깐 0으로 두고 글 높이를 잼 (+ 위아래 테두리 2)
  const measure = () => {
    if (!isWeb) return;
    requestAnimationFrame(() => {
      const el = input.current as unknown as HTMLTextAreaElement | null;
      if (!el) return;
      const before = el.style.height;
      el.style.height = '0px'; // auto는 textarea 기본 두 줄 높이가 남음
      const h = el.scrollHeight + 2;
      el.style.height = before; // 높이가 같으면 다시 그리지 않으므로 되돌려 둠
      setHeight(h);
    });
  };
  const change = (t: string) => {
    setText(t);
    if (t) setTip(false);
    measure();
  };
  return (
    <View style={{ gap: 8 }}>
      {tip && (
        <Card tone="info" style={{ gap: 6 }}>
          <Text style={T.body} accessibilityLiveRegion="polite">
            {c.dictationTip}
          </Text>
          <Btn label={c.dictationNever} kind="ghost" onPress={never} />
        </Card>
      )}
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
        <TextInput
          ref={input}
          value={text}
          onChangeText={change}
          onBlur={() => (blurTimer.current = setTimeout(() => setTip(false), 300))} // 바로 닫으면 안내 안 버튼을 누른 게 먹히지 않음 (웹)
          onKeyPress={key}
          placeholder={c.placeholder}
          placeholderTextColor={C.text3}
          multiline
          maxLength={MAX_LENGTH}
          style={{ flex: 1, minHeight: L.touch, maxHeight: INPUT_MAX, ...(isWeb ? { height: Math.min(INPUT_MAX, Math.max(L.touch, height)) } : null), borderWidth: 1, borderColor: C.border, borderRadius: R.control, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, color: C.text, backgroundColor: C.card }}
        />
        {hasText ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={c.send}
            accessibilityState={{ disabled: !ready }}
            onPress={send}
            style={{ width: L.touch, height: L.touch, borderRadius: L.touch / 2, backgroundColor: ready ? C.p600 : C.muted, alignItems: 'center', justifyContent: 'center' }}
          >
            <Text style={{ fontSize: 20, fontWeight: '700', color: ready ? C.onPrimary : C.text3 }}>↑</Text>
          </Pressable>
        ) : (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={c.dictation}
            onPress={dictate}
            style={{ width: L.touch, height: L.touch, alignItems: 'center', justifyContent: 'center' }}
          >
            <MicIcon />
          </Pressable>
        )}
      </View>
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
