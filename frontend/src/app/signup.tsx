import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import type { Sex } from '@/features/common/api';
import { useAuth } from '@/features/common/auth';
import { DRINKING, SMOKING, type Drinking, type Smoking } from '@/features/common/health';
import { ApiError } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { C, T } from '@/shared/theme';
import { Btn, Card, Check, Field, Radio, Screen, Section } from '@/shared/ui';

const c = copy.signup;

// CM-02 회원가입, CM-02-E1 입력 오류 (API 명세서 v1.5 초안 A-1). 별명은 받지 않음 (#96)
// 가입 때는 흡연, 음주만 받고 나머지 건강 정보는 내 정보에서 (10/14 회의)
export default function Signup() {
  const { signup } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [birthYear, setBirthYear] = useState('');
  const [sex, setSex] = useState<Sex | null>(null);
  const [smoking, setSmoking] = useState<Smoking | null>(null);
  const [drinking, setDrinking] = useState<Drinking | null>(null);
  const [terms, setTerms] = useState(false);
  const [privacy, setPrivacy] = useState(false);
  const [sensitive, setSensitive] = useState(false);
  const [fieldError, setFieldError] = useState<{ field: string; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preparing, setPreparing] = useState(false); // 동의 상세(보기)는 이번 범위 밖

  const mismatch = confirm !== '' && confirm !== password;
  const errorOf = (field: string) => (fieldError?.field === field ? fieldError.message : undefined);
  const canSubmit =
    !busy &&
    email.trim() !== '' &&
    password !== '' &&
    !mismatch &&
    confirm !== '' &&
    /^\d{4}$/.test(birthYear) &&
    sex !== null &&
    smoking !== null &&
    drinking !== null &&
    terms &&
    privacy &&
    sensitive;

  const submit = async () => {
    if (!canSubmit || sex === null || smoking === null || drinking === null) return;
    setBusy(true);
    setFieldError(null);
    setError(null);
    try {
      await signup({
        email: email.trim(),
        password,
        birthYear: Number(birthYear),
        sex,
        health: { smoking, drinking },
        consents: { terms, privacy, sensitiveHealth: sensitive },
      });
    } catch (e) {
      if (e instanceof ApiError && e.field) setFieldError({ field: e.field, message: e.message });
      else setError(e instanceof ApiError ? e.message : copy.common.serverError);
    } finally {
      setBusy(false);
    }
  };

  const view = (
    <Pressable accessibilityRole="button" hitSlop={8} onPress={() => setPreparing(true)}>
      <Text style={[T.bodyM, { color: C.p700 }]}>{c.view}</Text>
    </Pressable>
  );

  return (
    <Screen title={c.title} footer={<Btn label={c.submit} disabled={!canSubmit} onPress={submit} />}>
      <Section title={c.account}>
        <Field
          label={c.email}
          value={email}
          onChangeText={setEmail}
          placeholder={copy.login.emailPlaceholder}
          keyboardType="email-address"
          error={errorOf('email')}
        />
        <Field
          label={c.password}
          value={password}
          onChangeText={setPassword}
          secure
          helper={c.passwordHelper}
          error={errorOf('password')}
        />
        <Field
          label={c.passwordConfirm}
          value={confirm}
          onChangeText={setConfirm}
          secure
          error={mismatch ? c.passwordMismatch : undefined}
        />
      </Section>

      <Section title={c.basic}>
        <Field
          label={c.birthYear}
          value={birthYear}
          onChangeText={(v) => setBirthYear(v.replace(/\D/g, '').slice(0, 4))}
          placeholder="1958"
          keyboardType="number-pad"
          helper={c.birthYearHelper}
          error={errorOf('birthYear')}
        />
        <Text style={T.label}>{c.sex}</Text>
        <View style={{ flexDirection: 'row' }}>
          <Radio on={sex === 'M'} label={c.male} onPress={() => setSex('M')} />
          <Radio on={sex === 'F'} label={c.female} onPress={() => setSex('F')} />
        </View>
        {errorOf('sex') && <Text style={{ fontSize: 14, color: C.danger }}>※ {errorOf('sex')}</Text>}
      </Section>

      <Section title={c.smoking}>
        <Text style={[T.body, { color: C.text2 }]}>{c.smokingQuestion}</Text>
        {SMOKING.map((v) => (
          <Radio key={v} on={smoking === v} label={copy.health.smoking[v]} onPress={() => setSmoking(v)} />
        ))}
        {errorOf('health.smoking') && (
          <Text style={{ fontSize: 14, color: C.danger }}>※ {errorOf('health.smoking')}</Text>
        )}
      </Section>

      <Section title={c.drinking}>
        <Text style={[T.body, { color: C.text2 }]}>{c.drinkingQuestion}</Text>
        {DRINKING.map((v) => (
          <Radio key={v} on={drinking === v} label={copy.health.drinking[v]} onPress={() => setDrinking(v)} />
        ))}
        {errorOf('health.drinking') && (
          <Text style={{ fontSize: 14, color: C.danger }}>※ {errorOf('health.drinking')}</Text>
        )}
      </Section>
      <Text style={[T.caption, { marginTop: 12 }]}>{c.later}</Text>

      <Section title={c.consents}>
        <Card style={{ gap: 4 }}>
          <Check on={terms} label={c.terms} onPress={() => setTerms(!terms)} right={view} />
          <Check on={privacy} label={c.privacy} onPress={() => setPrivacy(!privacy)} right={view} />
          <Check on={sensitive} label={c.sensitiveHealth} onPress={() => setSensitive(!sensitive)} right={view} />
          <Text style={T.caption}>{c.sensitiveBody}</Text>
          {preparing && <Text style={T.caption}>{copy.preparing}</Text>}
          {fieldError?.field.startsWith('consents.') && (
            <Text style={{ fontSize: 14, color: C.danger }}>※ {fieldError.message}</Text>
          )}
        </Card>
      </Section>
      {error && <Text style={{ fontSize: 14, color: C.danger, marginTop: 12 }}>※ {error}</Text>}
    </Screen>
  );
}
