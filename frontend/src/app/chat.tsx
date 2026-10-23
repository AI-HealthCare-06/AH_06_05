import { useRouter } from 'expo-router';
import { Fragment, useEffect, useRef, type ReactNode } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useChatLauncher } from '@/features/chatbot/launcher';
import {
  AnswerBubble,
  Composer,
  ContextCard,
  Empty,
  ErrorCard,
  FollowUps,
  Generating,
  SafetyCards,
  SafetyLine,
  SuggestChips,
  UserBubble,
} from '@/features/chatbot/parts';
import { useChat, type Pending } from '@/features/chatbot/useChat';
import type { Message } from '@/features/chatbot/types';
import { copy } from '@/shared/copy';
import { C, S, T } from '@/shared/theme';
import { Btn, Screen } from '@/shared/ui';

const c = copy.chatbot;

// CB-01 챗봇 창 (1단계): E1 첫 대화, 대화, E2 맥락 카드, E4, E5, E6 (설계 메모 4-2 ~ 4-8 항목, #100)
export default function Chat() {
  const router = useRouter();
  const ins = useSafeAreaInsets();
  const { chatParams } = useChatLauncher();
  const chat = useChat(chatParams);
  const scroll = useRef<ScrollView>(null);

  useEffect(() => {
    scroll.current?.scrollToEnd({ animated: true });
  }, [chat.messages, chat.pending]);

  // 서버 질문 줄 번호 → 그 질문에 걸린 실패 (답 줄이 지워졌거나 30초가 지남)
  const failedByQuestion = new Map<number, Pending>();
  for (const q of chat.pending) if (q.error && q.questionId !== undefined) failedByQuestion.set(q.questionId, q);
  const failedAnswers = new Set(chat.pending.filter((q) => q.error).map((q) => q.answerId));
  const shown = new Set(chat.messages.map((m) => m.id));

  // 서버 목록에 아직 없는 질문 (보내는 중, H-1이나 H-3 단계 실패)
  const local = chat.pending.filter((q) => q.questionId === undefined || !shown.has(q.questionId));

  const row = (m: Message): ReactNode => {
    if (m.contextCard) return <ContextCard analysisId={m.contextCard.analysisId} context={m.contextCard.context} />;
    if (m.role === 'user') {
      if (chat.hidden.includes(m.id)) return null;
      const failed = failedByQuestion.get(m.id);
      const text = m.content || chat.texts[m.id];
      return (
        <>
          {text ? <UserBubble text={text} /> : <UserBubble text={c.restoredQuestion} faded />}
          {failed?.error && <ErrorCard kind={failed.error} onRetry={() => chat.retry(failed.crid)} />}
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
        />
      );
    }
    if (m.status === 'generating') return failedAnswers.has(m.id) ? null : <Generating />;
    return <AnswerBubble m={m} />;
  };

  // 꼬리질문은 마지막 줄이 실제 답일 때만 (재질문, 긴급, 자해, 오류에는 없음). 다음 메시지가 오가면 사라짐
  const last = chat.messages[chat.messages.length - 1];
  const followAfter =
    local.length === 0 && !chat.pendingCard && last?.status === 'done' && ['normal', 'partial', 'no_evidence', 'refer'].includes(last.answerType ?? '')
      ? last.id
      : null;
  const asked = new Set(chat.messages.filter((m) => m.role === 'user').map((m) => m.content || chat.texts[m.id]));

  const empty = !chat.loading && chat.messages.length === 0 && local.length === 0 && !chat.pendingCard;

  return (
    <Screen title={c.title} onBack={() => router.back()} scroll={false}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView ref={scroll} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: S.side, gap: S.gap }}>
          {chat.todayFailed && (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={[T.caption, { flex: 1 }]}>{c.todayFail}</Text>
              <Btn label={c.reload} kind="ghost" onPress={() => void chat.open()} />
            </View>
          )}
          {chat.loading && <ActivityIndicator color={C.p600} style={{ marginTop: 40 }} />}
          {empty && <Empty hasHistory={chat.todayFailed ? null : chat.hasHistory} onPick={chat.ask} disabled={chat.busy} />}
          {chat.messages.map((m) => (
            <Fragment key={m.id}>
              {row(m)}
              {m.id === followAfter && <FollowUps asked={asked} onPick={chat.ask} disabled={chat.busy} />}
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
              {q.error ? <ErrorCard kind={q.error} onRetry={() => chat.retry(q.crid)} /> : <Generating />}
            </Fragment>
          ))}
        </ScrollView>
        <View style={{ paddingHorizontal: S.side, paddingTop: 8, paddingBottom: ins.bottom + 12, backgroundColor: C.card, borderTopWidth: 1, borderTopColor: C.border }}>
          {chat.safetyMode && <SafetyLine />}
          <Composer onSend={chat.ask} busy={chat.busy || chat.loading} />
        </View>
      </KeyboardAvoidingView>
    </Screen>
  );
}
