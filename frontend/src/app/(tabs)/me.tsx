import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { deleteAllSessions } from '@/features/chatbot/api';
import { getMe, type Me as MeInfo } from '@/features/common/api';
import { logout } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { clearFailed } from '@/shared/storage/chat';
import { C, L, T } from '@/shared/theme';
import { Btn, Card, Confirm, Screen, Section } from '@/shared/ui';

const c = copy.me;

function Row({ k, v }: { k: string; v: string }) {
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 12 }}>
      <Text style={[T.body, { color: C.text2 }]}>{k}</Text>
      <Text style={[T.bodyM, { flexShrink: 1, textAlign: 'right' }]}>{v}</Text>
    </View>
  );
}

// CM-05 내 정보 (API 명세서 v1.5 초안 U-1). 화면에 다시 들어올 때마다 새로 읽음 (CM-06에서 저장한 뒤)
export default function Me() {
  const router = useRouter();
  const [me, setMe] = useState<MeInfo | null>(null);
  const [failed, setFailed] = useState(false);
  const [asking, setAsking] = useState(false); // MY-S1-E1 전체 삭제 확인
  const [notice, setNotice] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      getMe()
        .then((m) => alive && (setMe(m), setFailed(false)))
        .catch(() => alive && setFailed(true));
      return () => {
        alive = false;
      };
    }, []),
  );

  const removeChats = async () => {
    setAsking(false);
    try {
      await deleteAllSessions();
      await clearFailed(); // 기기에 남긴 실패한 질문도
      setNotice(c.chatsDeleted);
    } catch {
      setNotice(c.chatsDeleteFail);
    }
  };

  const h = me?.health;
  const or = (v: string | null | undefined) => v ?? c.none;
  return (
    // 아래 내비와 떠 있는 챗봇 버튼이 있는 화면이라, 수정 버튼은 챗봇 버튼에 가리지 않게 맨 위에 둠
    <Screen title={c.title} back={false} fab>
      {failed && <Text style={{ fontSize: 14, color: C.danger }}>※ {c.loadFailed}</Text>}
      {me && h && (
        <>
          <Btn label={c.edit} kind="secondary" onPress={() => router.push('/me-edit')} />
          <Section title={c.account}>
            <Card style={{ gap: 12 }}>
              <Row k={c.email} v={me.email} />
              <Row k={c.birthYear} v={c.birthYearValue(me.birthYear)} />
              <Row k={c.sex} v={me.sex === 'F' ? copy.signup.female : copy.signup.male} />
            </Card>
          </Section>
          <Section title={c.health}>
            <Text style={T.caption}>{c.healthNote}</Text>
            <Card style={{ gap: 12 }}>
              <Row k={c.smoking} v={copy.health.smoking[h.smoking]} />
              <Row k={c.drinking} v={copy.health.drinking[h.drinking]} />
              <Row k={c.diseases} v={h.diseases.length ? h.diseases.map((d) => copy.health.diseases[d]).join(', ') : c.none} />
              {me.sex === 'F' && <Row k={c.pregnant} v={or(h.pregnant && copy.health.pregnant[h.pregnant])} />}
              <Row k={c.dialysis} v={or(h.dialysis && copy.health.dialysis[h.dialysis])} />
              <Row
                k={c.body}
                v={h.heightCm || h.weightKg ? `${h.heightCm ? `${h.heightCm}cm` : '-'}, ${h.weightKg ? `${h.weightKg}kg` : '-'}` : c.none}
              />
              <Row
                k={c.exams}
                v={h.upcomingExams.length ? h.upcomingExams.map((e) => `${e.name}, ${c.examDateValue(e.date)}`).join(' / ') : c.none}
              />
            </Card>
          </Section>
          <Section title={c.consentAccount}>
            <Card style={{ gap: 4 }}>
              {(
                [
                  [c.consentHistory, '/consents'],
                  [c.withdraw, '/withdraw'],
                ] as const
              ).map(([label, href]) => (
                <Pressable
                  key={label}
                  accessibilityRole="button"
                  onPress={() => router.push(href)}
                  style={{ minHeight: L.touch, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}
                >
                  <Text style={T.body}>{label}</Text>
                  <Text style={[T.body, { color: C.text3 }]}>›</Text>
                </Pressable>
              ))}
              {/* 확인 창 없이 바로: 다시 로그인하면 그대로 이어서 쓸 수 있어서 (11/4, 와이어프레임 CM-05 ⑥) */}
              <Pressable accessibilityRole="button" onPress={() => void logout()} style={{ minHeight: L.touch, justifyContent: 'center' }}>
                <Text style={T.body}>{c.logout}</Text>
              </Pressable>
              <Pressable accessibilityRole="button" onPress={() => setAsking(true)} style={{ minHeight: L.touch, justifyContent: 'center' }}>
                <Text style={[T.body, { color: C.danger }]}>{c.chatsDelete}</Text>
              </Pressable>
            </Card>
            {notice && <Text style={T.caption}>{notice}</Text>}
          </Section>
          <Confirm
            visible={asking}
            title={c.chatsDeleteTitle}
            body={c.chatsDeleteBody}
            ok={copy.chatbot.sessionDelete}
            onOk={() => void removeChats()}
            onCancel={() => setAsking(false)}
          />
        </>
      )}
    </Screen>
  );
}
