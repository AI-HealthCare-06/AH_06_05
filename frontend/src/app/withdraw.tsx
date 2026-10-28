import { useState } from 'react';
import { Text, View } from 'react-native';

import { withdrawMe } from '@/features/common/api';
import { ApiError, forgetLogin } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { C, T } from '@/shared/theme';
import { Btn, Card, Check, Screen } from '@/shared/ui';

const c = copy.me;

// CM-07 회원 탈퇴 (API 명세서 U-3). 확인에 체크해야 버튼이 켜지고, 끝나면 로그인 화면으로 감
export default function Withdraw() {
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!checked || busy) return;
    setBusy(true);
    setError(null);
    try {
      await withdrawMe();
      await forgetLogin(); // 저장한 출입증을 지우고 로그인 화면으로
    } catch (e) {
      setError(e instanceof ApiError ? e.message : copy.common.serverError);
      setBusy(false);
    }
  };

  return (
    <Screen title={c.withdrawTitle}>
      <Text style={T.body}>{c.withdrawLead}</Text>
      <Card style={{ gap: 8 }}>
        {c.withdrawList.map((line) => (
          <View key={line} style={{ flexDirection: 'row', gap: 8 }}>
            <Text style={T.body}>-</Text>
            <Text style={[T.body, { flex: 1 }]}>{line}</Text>
          </View>
        ))}
      </Card>
      <Check on={checked} label={c.withdrawCheck} onPress={() => setChecked((v) => !v)} bold />
      {error && <Text style={{ fontSize: 14, color: C.danger }}>※ {error}</Text>}
      <Btn label={c.withdrawOk} kind="danger" disabled={!checked || busy} onPress={submit} />
    </Screen>
  );
}
