import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { LOGIN_LOCK_MINUTES, LOGIN_MAX_FAILURES, useAuth } from '@/features/common/auth';
import { ApiError } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { C, T } from '@/shared/theme';
import { Btn, Card, Chip, Field, Screen } from '@/shared/ui';

function toMmss(ms: number) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

// CM-01 로그인, CM-01-E1 로그인 실패, CM-01-E2 로그인 잠김 (프로토타입 Login 화면, API 명세서 A-2)
export default function Login() {
  const { login, notice } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [failures, setFailures] = useState(0); // 서버가 알려 준 틀린 횟수 (E1)
  const [failMessage, setFailMessage] = useState<string | null>(null); // 횟수 없이 받은 실패 문구
  const [error, setError] = useState<string | null>(null); // 연결 오류 등 나머지
  const [signupNotice, setSignupNotice] = useState(false);
  const [lockedUntil, setLockedUntil] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const [busy, setBusy] = useState(false);

  const locked = lockedUntil !== null && lockedUntil > now;

  useEffect(() => {
    if (lockedUntil === null) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [lockedUntil]);

  useEffect(() => {
    if (lockedUntil !== null && lockedUntil <= now) {
      setLockedUntil(null); // 잠김이 풀리면 서버도 1번째 실패부터 다시 셈
      setFailures(0);
    }
  }, [lockedUntil, now]);

  const submit = async () => {
    if (busy || locked) return;
    setBusy(true);
    setError(null);
    setFailMessage(null);
    try {
      await login(email.trim(), password);
    } catch (e) {
      if (!(e instanceof ApiError)) {
        setError(copy.common.serverError);
      } else if (e.code === 'AUTH_INVALID_CREDENTIALS') {
        const left = e.detail?.remainingAttempts;
        if (typeof left === 'number') {
          setFailures(LOGIN_MAX_FAILURES - left);
        } else {
          setFailures(0); // 서버는 계정마다 세므로 다른 이메일이면 앞의 횟수를 지움
          setFailMessage(e.message);
        }
        setPassword('');
      } else if (e.code === 'AUTH_LOCKED') {
        const until = Date.parse(String(e.detail?.lockedUntil));
        setLockedUntil(Number.isNaN(until) ? Date.now() + LOGIN_LOCK_MINUTES * 60 * 1000 : until);
        setNow(Date.now());
        setPassword('');
      } else {
        setError(e.message);
      }
    } finally {
      setBusy(false);
    }
  };

  const mmss = toMmss((lockedUntil ?? 0) - now);
  const canSubmit = !busy && !locked && email.trim() !== '' && password !== '';

  return (
    <Screen
      title={copy.login.title}
      back={false}
      footer={
        <Btn
          label={locked ? copy.login.lockedSubmit(mmss) : copy.login.submit}
          disabled={!canSubmit}
          onPress={submit}
        />
      }
    >
      {notice && (
        <Card tone="info" style={{ marginBottom: 8 }}>
          <Text style={T.bodyM}>{notice}</Text>
        </Card>
      )}
      <View style={st.brand}>
        <View style={st.logo}>
          <Text style={st.logoText}>약</Text>
        </View>
        <Text style={T.title}>{copy.appName}</Text>
        <Text style={[T.body, { color: C.text2, textAlign: 'center' }]}>{copy.login.tagline}</Text>
      </View>

      {locked ? (
        <Card tone="danger" style={{ marginTop: 32, gap: 8 }}>
          <View style={st.lockedHead}>
            <Text style={T.subhead}>{copy.login.lockedTitle}</Text>
            <Chip label={copy.login.lockedChip} tone="danger" />
          </View>
          <Text style={T.body}>{copy.login.lockedBody(LOGIN_MAX_FAILURES, LOGIN_LOCK_MINUTES)}</Text>
          <Text style={T.bodyM}>{copy.login.lockedLeft(mmss)}</Text>
        </Card>
      ) : (
        <View style={{ gap: 16, marginTop: 32 }}>
          <Field
            label={copy.login.email}
            value={email}
            onChangeText={setEmail}
            placeholder={copy.login.emailPlaceholder}
            keyboardType="email-address"
          />
          <Field
            label={copy.login.password}
            value={password}
            onChangeText={setPassword}
            placeholder={copy.login.passwordPlaceholder}
            secure
          />
          {failures > 0 && (
            <View style={{ gap: 4 }}>
              <Text style={st.danger}>※ {copy.login.failed(failures, LOGIN_MAX_FAILURES)}</Text>
              <Text style={st.danger}>※ {copy.login.lockWarning(LOGIN_MAX_FAILURES, LOGIN_LOCK_MINUTES)}</Text>
            </View>
          )}
          {failMessage && <Text style={st.danger}>※ {failMessage}</Text>}
          {error && <Text style={st.danger}>※ {error}</Text>}
          <View style={st.signupRow}>
            <Text style={T.body}>{copy.login.noAccount}</Text>
            {/* CM-02 회원가입은 다음 작업. 그 전에는 준비 중 안내만 */}
            <Pressable accessibilityRole="button" hitSlop={8} onPress={() => setSignupNotice(true)}>
              <Text style={[T.bodyM, { color: C.p700 }]}>{copy.login.signup}</Text>
            </Pressable>
          </View>
          {signupNotice && <Text style={[T.caption, { textAlign: 'center' }]}>{copy.preparing}</Text>}
        </View>
      )}
    </Screen>
  );
}

const st = StyleSheet.create({
  brand: { alignItems: 'center', marginTop: 24, gap: 10 },
  logo: { width: 72, height: 72, borderRadius: 20, backgroundColor: C.p600, alignItems: 'center', justifyContent: 'center' },
  logoText: { color: C.onPrimary, fontSize: 30, fontWeight: '800' },
  lockedHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  danger: { fontSize: 14, color: C.danger },
  signupRow: { flexDirection: 'row', justifyContent: 'center', gap: 8, marginTop: 8 },
});
