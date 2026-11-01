import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Text, View } from 'react-native';

import { agreeConsentAgain, getConsents, withdrawConsent, type ConsentItem } from '@/features/common/api';
import { ApiError } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { clearFailed } from '@/shared/storage/chat';
import { C, T } from '@/shared/theme';
import { Btn, Card, Confirm, Screen, Section } from '@/shared/ui';

const c = copy.me;

// 2026-09-20T10:00:00+09:00 처럼 서버가 준 시각에서 날짜만 (한국 시간이라 앞 10글자가 그날)
const day = (iso: string) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[1]}년 ${Number(m[2])}월 ${Number(m[3])}일` : iso;
};

// CM-05 동의 내역 (API 명세서 U-4, U-5, U-6). 건강 정보 동의만 철회하고 다시 켤 수 있음.
// 켤 때는 민감정보라 동의 글을 다시 보여 주고 [동의하기]를 눌러야 함 (#137)
export default function Consents() {
  const [items, setItems] = useState<ConsentItem[] | null>(null);
  const [notice, setNotice] = useState<{ text: string; error: boolean } | null>(null);
  const [asking, setAsking] = useState(false);
  const [askingAgain, setAskingAgain] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems((await getConsents()).items);
    } catch (e) {
      setNotice({ text: e instanceof ApiError ? e.message : c.consentLoadFailed, error: true });
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const confirm = async () => {
    if (busy) return;
    setBusy(true);
    setAsking(false);
    try {
      await withdrawConsent();
      await clearFailed(); // 기기에 남긴 실패한 챗봇 질문도 지움
      setNotice({ text: c.consentDone, error: false });
      await load();
    } catch (e) {
      setNotice({ text: e instanceof ApiError ? e.message : copy.common.serverError, error: true });
    } finally {
      setBusy(false);
    }
  };

  const agreeAgain = async () => {
    if (busy) return;
    setBusy(true);
    setAskingAgain(false);
    try {
      await agreeConsentAgain();
      setNotice({ text: c.consentAgainDone, error: false });
      await load();
    } catch (e) {
      setNotice({ text: e instanceof ApiError ? e.message : copy.common.serverError, error: true });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen title={c.consentsTitle}>
      {notice && <Text style={{ fontSize: 14, color: notice.error ? C.danger : C.text2 }}>※ {notice.text}</Text>}
      {items && (
        <Section title={c.consentAccount}>
          <Card style={{ gap: 16 }}>
            {items.map((it) => (
              <View key={it.type} style={{ gap: 4 }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 12 }}>
                  <Text style={[T.bodyM, { flexShrink: 1 }]}>{c.consentName[it.type]}</Text>
                  <Text style={[T.bodyM, { color: it.agreed ? C.p700 : C.danger }]}>
                    {it.agreed ? c.consentAgreed : c.consentWithdrawn}
                  </Text>
                </View>
                {it.agreedAt && <Text style={T.caption}>{c.consentAgreedAt(day(it.agreedAt))}</Text>}
                {it.withdrawnAt && <Text style={T.caption}>{c.consentWithdrawnAt(day(it.withdrawnAt))}</Text>}
              </View>
            ))}
          </Card>
          {items.some((it) => it.type === 'sensitiveHealth' && it.agreed) && (
            <>
              <Text style={T.caption}>{c.consentWithdrawNote}</Text>
              <Btn label={c.consentWithdrawBtn} kind="danger" disabled={busy} onPress={() => setAsking(true)} />
            </>
          )}
          {items.some((it) => it.type === 'sensitiveHealth' && !it.agreed) && (
            <>
              <Text style={T.caption}>{c.consentAgainNote}</Text>
              <Btn label={c.consentAgainBtn} disabled={busy} onPress={() => setAskingAgain(true)} />
            </>
          )}
        </Section>
      )}
      <Confirm
        visible={asking}
        title={c.consentConfirmTitle}
        body={c.consentConfirmBody}
        ok={c.consentConfirmOk}
        onOk={confirm}
        onCancel={() => setAsking(false)}
      />
      <Confirm
        visible={askingAgain}
        title={c.consentAgainTitle}
        body={c.consentAgainBody}
        ok={c.consentAgainOk}
        danger={false}
        onOk={agreeAgain}
        onCancel={() => setAskingAgain(false)}
      />
    </Screen>
  );
}
