import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, Text, View } from 'react-native';

import { deleteSession, getSessionsOn, renameSession } from '@/features/chatbot/api';
import { dayLabel, startTime } from '@/features/chatbot/time';
import type { SessionItem } from '@/features/chatbot/types';
import { copy } from '@/shared/copy';
import { C, L, R, S, T } from '@/shared/theme';
import { Btn, Card, Confirm, Field, Screen } from '@/shared/ui';

const c = copy.chatbot;
const TITLE_MAX = 30; // 명세서 H-5

function TextBtn({ label, color, onPress }: { label: string; color: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={{ minHeight: L.touch, justifyContent: 'center', paddingRight: 16 }}>
      <Text style={[T.label, { color }]}>{label}</Text>
    </Pressable>
  );
}

// 제목 수정 팝업: 비어 있거나 공백뿐이면 [저장]을 막음 (설계 메모 4-13)
function RenameDialog({ item, onSave, onClose }: { item: SessionItem; onSave: (title: string) => void; onClose: () => void }) {
  const [title, setTitle] = useState(item.title);
  const clean = title.trim();
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: C.dim, justifyContent: 'center', padding: S.side }}>
        <View style={{ backgroundColor: C.card, borderRadius: R.card, padding: S.side, gap: 10 }} accessibilityViewIsModal>
          <Field label={c.titleEdit} value={title} onChangeText={(v) => setTitle(v.slice(0, TITLE_MAX))} helper={`${title.length}/${TITLE_MAX}`} />
          <Btn label={c.titleSave} disabled={!clean} onPress={() => onSave(clean)} />
          <Btn label={copy.common.cancel} kind="secondary" onPress={onClose} />
        </View>
      </View>
    </Modal>
  );
}

// CB-03 날짜별 대화 목록 (설계 메모 4-13, 명세서 H-4 ?date=, H-5, H-6). 카드를 누르면 그 대화를 열고 이어서 질문
export default function ChatHistoryDay() {
  const router = useRouter();
  const { date, current } = useLocalSearchParams<{ date: string; current?: string }>();
  const [items, setItems] = useState<SessionItem[]>([]);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [editing, setEditing] = useState<SessionItem | null>(null);
  const [removing, setRemoving] = useState<SessionItem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    let alive = true;
    getSessionsOn(date)
      .then((list) => {
        if (!alive) return;
        setItems(list);
        setState('ready');
      })
      .catch(() => alive && setState('error'));
    return () => {
      alive = false;
    };
  }, [date]);

  // 지난 대화에서 돌아왔을 때도 다시 읽음
  useFocusEffect(load);

  const save = async (title: string) => {
    const target = editing;
    setEditing(null);
    if (!target) return;
    try {
      await renameSession(target.sessionId, title);
      setItems((list) => list.map((i) => (i.sessionId === target.sessionId ? { ...i, title } : i)));
      setNotice(null);
    } catch {
      setNotice(c.titleFail);
    }
  };

  const remove = async () => {
    const target = removing;
    setRemoving(null);
    if (!target) return;
    try {
      await deleteSession(target.sessionId);
      setNotice(null);
      const rest = items.filter((i) => i.sessionId !== target.sessionId);
      setItems(rest);
      if (rest.length === 0) router.back(); // 그날 대화가 모두 지워지면 달력으로
    } catch {
      setNotice(c.deleteFail);
    }
  };

  const isCurrent = removing !== null && current === String(removing.sessionId);
  return (
    <Screen title={c.dayTitle(dayLabel(date))}>
      <View style={{ gap: 12 }}>
        <Text style={T.caption}>{c.dayGuide}</Text>
        {notice && <Text style={{ fontSize: 14, color: C.danger }}>※ {notice}</Text>}
        {state === 'loading' && <ActivityIndicator color={C.p600} />}
        {state === 'error' && (
          <View style={{ gap: 8 }}>
            <Text style={[T.body, { color: C.danger }]}>{c.historyFail}</Text>
            <Btn label={c.reload} kind="secondary" onPress={load} />
          </View>
        )}
        {items.map((i) => (
          <Card key={i.sessionId} style={{ gap: 4 }}>
            <Pressable
              accessibilityRole="button"
              onPress={() => router.push({ pathname: '/chat', params: { sessionId: i.sessionId } })}
              style={{ gap: 4, minHeight: L.touch }}
            >
              <Text style={T.bodyM} numberOfLines={2}>
                {i.title}
              </Text>
              <Text style={T.caption}>{startTime(i.createdAt)}</Text>
              {!!i.preview && i.preview !== i.title && (
                <Text style={[T.body, { color: C.text2 }]} numberOfLines={2}>
                  {i.preview}
                </Text>
              )}
            </Pressable>
            <View style={{ flexDirection: 'row' }}>
              <TextBtn label={c.titleEdit} color={C.p700} onPress={() => setEditing(i)} />
              <TextBtn label={c.sessionDelete} color={C.danger} onPress={() => setRemoving(i)} />
            </View>
          </Card>
        ))}
      </View>
      {editing && <RenameDialog item={editing} onSave={(t) => void save(t)} onClose={() => setEditing(null)} />}
      <Confirm
        visible={removing !== null}
        title={c.deleteTitle}
        body={isCurrent ? `${c.deleteBody}\n${c.deleteCurrent}` : c.deleteBody}
        ok={c.sessionDelete}
        onOk={() => void remove()}
        onCancel={() => setRemoving(null)}
      />
    </Screen>
  );
}
