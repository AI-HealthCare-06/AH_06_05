import { useLocalSearchParams, useRouter } from 'expo-router';
import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View, type LayoutChangeEvent } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useChatLauncher } from '@/features/chatbot/launcher';
import {
  AnswerBubble,
  AttachSheet,
  Composer,
  ContextCard,
  Empty,
  ErrorCard,
  FollowUps,
  Generating,
  PhotoDraftBar,
  QuoteLine,
  ResentCard,
  SafetyCards,
  SafetyLine,
  SuggestChips,
  UserBubble,
} from '@/features/chatbot/parts';
import { pickFile, pickPhoto, takePhoto, type PickResult } from '@/features/chatbot/attach';
import { stopSpeaking } from '@/features/chatbot/speech';
import { useChat, type Pending } from '@/features/chatbot/useChat';
import type { Message } from '@/features/chatbot/types';
import { copy } from '@/shared/copy';
import { C, L, S, T } from '@/shared/theme';
import { Btn, Screen } from '@/shared/ui';
import { CalendarIcon } from '@/shared/ui/icons';

const c = copy.chatbot;

// CB-01 챗봇 창 (1단계): E1 첫 대화, 대화, E2 맥락 카드, E4, E5, E6 (설계 메모 4-2 ~ 4-8 항목, #100)
export default function Chat() {
  const router = useRouter();
  const ins = useSafeAreaInsets();
  const { chatParams } = useChatLauncher();
  // CB-03에서 연 지난 대화는 주소로 받음: 아래에 남은 오늘 대화 창이 함께 바뀌지 않게
  const { sessionId: past } = useLocalSearchParams<{ sessionId?: string }>();
  const params = useMemo(() => (past ? { from: 'CB-03' as const, sessionId: Number(past) } : chatParams), [past, chatParams]);
  const chat = useChat(params);
  const scroll = useRef<ScrollView>(null);
  const [sheet, setSheet] = useState(false); // CB-04 첨부 메뉴
  const [pickNote, setPickNote] = useState<string | null>(null);
  // 창을 닫거나 달력으로 가면 읽기를 멈춤 (설계 메모 4-11)
  useEffect(() => () => stopSpeaking(), []);

  // 새 줄이 생기면 맨 아래로. 이미 있던 맥락 카드로 들어왔으면 그 카드에 머묾 (설계 메모 3-4 항목)
  useEffect(() => {
    if (chat.focusCard === null) scroll.current?.scrollToEnd({ animated: true });
  }, [chat.messages, chat.pending, chat.focusCard]);
  const pick = async (how: 'camera' | 'library' | 'file') => {
    setSheet(false);
    setPickNote(null);
    const r: PickResult = await (how === 'camera' ? takePhoto() : how === 'library' ? pickPhoto() : pickFile());
    if (!r) return;
    if ('error' in r) {
      setPickNote({ permission: c.cameraDenied, tooBig: c.photoTooBig, type: c.photoType, fail: c.photoPick }[r.error]);
      return;
    }
    chat.attach(r.file);
  };
  const toCard = (e: LayoutChangeEvent) => scroll.current?.scrollTo({ y: e.nativeEvent.layout.y, animated: true });

  // 서버 질문 줄 번호 → 그 질문에 걸린 실패 (답 줄이 지워졌거나 30초가 지남)
  const failedByQuestion = new Map<number, Pending>();
  for (const q of chat.pending) if (q.error && q.questionId !== undefined) failedByQuestion.set(q.questionId, q);
  const failedAnswers = new Set(chat.pending.filter((q) => q.error).map((q) => q.answerId));
  const shown = new Set(chat.messages.map((m) => m.id));

  // 서버 목록에 아직 없는 질문 (보내는 중, H-1이나 H-3 단계 실패)
  const local = chat.pending.filter((q) => q.questionId === undefined || !shown.has(q.questionId));

  // 다시 시도한 질문의 답은 맨 아래에 새 줄로 생김 (서버 chats.ask). 바로 앞 줄이 그 질문이 아니면 옮겨 간 답
  const answerTo = new Map<number, Message>();
  for (const m of chat.messages) if (m.role === 'assistant' && m.replyTo !== undefined) answerTo.set(m.replyTo, m);
  const byId = new Map(chat.messages.map((m) => [m.id, m]));
  const questionText = (id: number) => {
    const q = byId.get(id);
    return q ? q.content || chat.texts[id] : undefined;
  };

  const row = (m: Message, i: number): ReactNode => {
    if (m.contextCard) {
      const card = <ContextCard analysisId={m.contextCard.analysisId} context={m.contextCard.context} />;
      return m.id === chat.focusCard ? <View onLayout={toCard}>{card}</View> : card;
    }
    if (m.role === 'user') {
      if (chat.hidden.includes(m.id)) return null;
      const failed = failedByQuestion.get(m.id);
      const text = m.content || chat.texts[m.id];
      const answer = answerTo.get(m.id);
      const moved = !failed?.error && answer !== undefined && chat.messages[i + 1]?.id !== answer.id;
      return (
        <>
          {text ? <UserBubble text={text} /> : <UserBubble text={c.restoredQuestion} faded />}
          {failed?.error && <ErrorCard kind={failed.error} onRetry={() => chat.retry(failed.crid)} />}
          {moved && <ResentCard />}
        </>
      );
    }
    if (m.safety) {
      // [지금은 증상이 없어요]는 가장 최근 차례에서만 (설계 메모 4-1 항목 "지난 차례의 버튼, 칩은 비활성화")
      // 실패해 남아 있는 예전 질문은 세지 않음 (보내는 중인 질문만)
      const latest = !local.some((q) => !q.error) && !chat.messages.some((x) => x.role === 'user' && x.id > m.id);
      const canResend = latest && m.replyTo !== undefined && !!chat.texts[m.replyTo];
      return (
        <SafetyCards
          safety={m.safety}
          relieved={chat.relieved.includes(m.id)}
          onNoSymptom={canResend ? () => chat.dismiss(m) : undefined}
          messageId={m.id}
        />
      );
    }
    const from = m.replyTo !== undefined && chat.messages[i - 1]?.id !== m.replyTo ? questionText(m.replyTo) : undefined;
    if (m.status === 'generating') {
      if (failedAnswers.has(m.id)) return null;
      return (
        <>
          {from && <QuoteLine text={from} />}
          <Generating since={chat.pending.find((q) => q.answerId === m.id)?.sentAt || Date.parse(m.createdAt) || undefined} />
        </>
      );
    }
    return (
      <>
        {from && <QuoteLine text={from} />}
        <AnswerBubble m={m} reveal={chat.isFresh(m.id)} />
      </>
    );
  };

  // 꼬리질문은 마지막 줄이 실제 답일 때만 (재질문, 긴급, 자해, 오류에는 없음). 다음 메시지가 오가면 사라짐
  const last = chat.messages[chat.messages.length - 1];
  const followAfter =
    local.length === 0 && !chat.pendingCard && last?.status === 'done' && ['normal', 'partial', 'no_evidence', 'refer'].includes(last.answerType ?? '')
      ? last.id
      : null;
  const asked = new Set(chat.messages.filter((m) => m.role === 'user').map((m) => m.content || chat.texts[m.id]));
  // 되물음 예상 답 칩도 마지막 답에만 (설계 메모 4-5). 누르면 그 글을 그대로 보냄
  const clarifyAfter = local.length === 0 && last?.status === 'done' && last.answerType === 'clarify' && last.chips?.length ? last.id : null;

  const empty = !chat.loading && chat.messages.length === 0 && local.length === 0 && !chat.pendingCard;

  return (
    <Screen
      title={c.title}
      onBack={() => router.back()}
      scroll={false}
      right={
        // 지난 대화에서는 둘 다 숨김: 챗봇 → 달력 → 목록 → 챗봇으로 쌓이지 않게 (설계 메모 4-1)
        past ? undefined : (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ disabled: chat.busy || chat.loading }}
              onPress={chat.busy || chat.loading ? undefined : chat.startNew}
              style={{ minHeight: L.touch, paddingHorizontal: 8, justifyContent: 'center', opacity: chat.busy || chat.loading ? 0.4 : 1 }}
            >
              <Text style={[T.label, { color: C.p700 }]}>{c.newChat}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={c.historyTitle}
              hitSlop={8}
              onPress={() => {
                stopSpeaking();
                router.push({ pathname: '/chat-history', params: chat.sessionId ? { current: chat.sessionId } : {} });
              }}
              style={{ width: L.touch, height: L.touch, alignItems: 'flex-end', justifyContent: 'center' }}
            >
              <CalendarIcon color={C.text2} />
            </Pressable>
          </View>
        )
      }
    >
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          ref={scroll}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ padding: S.side, gap: S.gap }}
          // 새 답이 글자 차례로 길어지고 출처, 피드백이 뒤에 붙어도 맨 아래를 따라감 (맥락 카드로 들어왔을 때는 그 카드에 머묾)
          onContentSizeChange={() => chat.focusCard === null && scroll.current?.scrollToEnd({ animated: false })}
        >
          {chat.todayFailed && (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={[T.caption, { flex: 1 }]}>{c.todayFail}</Text>
              <Btn label={c.reload} kind="ghost" onPress={() => void chat.open()} />
            </View>
          )}
          {chat.loading && <ActivityIndicator color={C.p600} style={{ marginTop: 40 }} />}
          {empty && <Empty hasHistory={chat.todayFailed ? null : chat.hasHistory} onPick={chat.ask} disabled={chat.busy} />}
          {chat.messages.map((m, i) => (
            <Fragment key={m.id}>
              {row(m, i)}
              {m.id === followAfter && <FollowUps asked={asked} onPick={chat.ask} disabled={chat.busy} />}
              {m.id === clarifyAfter && (
                <View style={{ gap: 8 }}>
                  <Text style={T.caption}>{c.clarifyChips}</Text>
                  <SuggestChips items={m.chips ?? []} onPick={chat.ask} disabled={chat.busy} />
                </View>
              )}
            </Fragment>
          ))}
          {chat.pendingCard && (
            <>
              <ContextCard analysisId={chat.pendingCard.analysisId} context={chat.pendingCard.context} />
              {!chat.pendingCard.context && <SuggestChips items={c.analysisChips} onPick={chat.ask} disabled={chat.busy} />}
            </>
          )}
          {local.map((q) => (
            <Fragment key={q.crid}>
              {!q.dismissed && <UserBubble text={q.content} />}
              {q.error ? <ErrorCard kind={q.error} onRetry={() => chat.retry(q.crid)} /> : <Generating since={q.sentAt} />}
            </Fragment>
          ))}
        </ScrollView>
        <View style={{ paddingHorizontal: S.side, paddingTop: 8, paddingBottom: ins.bottom + 12, backgroundColor: C.card, borderTopWidth: 1, borderTopColor: C.border }}>
          {chat.safetyMode && <SafetyLine />}
          {pickNote && <Text style={{ fontSize: 14, color: C.danger, marginBottom: 8 }}>※ {pickNote}</Text>}
          {chat.photo && (
            <View style={{ marginBottom: 8 }}>
              <PhotoDraftBar file={chat.photo.file} busy={chat.photo.busy} error={chat.photo.error} onSend={() => void chat.sendPhoto()} onDrop={chat.dropPhoto} />
            </View>
          )}
          <Composer onSend={chat.ask} busy={chat.busy || chat.loading} onAttach={() => setSheet(true)} />
          <AttachSheet visible={sheet} onPick={(how) => void pick(how)} onClose={() => setSheet(false)} />
        </View>
      </KeyboardAvoidingView>
    </Screen>
  );
}
