// 공통 부품 — 프로토타입 ui.tsx에서 가져옴 (안건 버튼 · 화면 ID 표시 · 프로토타입 메모는 뺌)
import { useRouter } from 'expo-router';
import type { ReactNode } from 'react';
import {
  KeyboardTypeOptions,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { copy } from '@/shared/copy';
import { C, L, R, S, T } from '@/shared/theme';

type BtnKind = 'primary' | 'secondary' | 'ghost' | 'danger';

export function Btn({
  label,
  onPress,
  kind = 'primary',
  disabled,
  style,
}: {
  label: string;
  onPress?: () => void;
  kind?: BtnKind;
  disabled?: boolean;
  style?: ViewStyle;
}) {
  const bg = disabled
    ? C.muted
    : kind === 'primary'
      ? C.p600
      : kind === 'danger'
        ? C.danger
        : kind === 'secondary'
          ? C.p50
          : 'transparent';
  const fg = disabled ? C.text3 : kind === 'primary' || kind === 'danger' ? C.onPrimary : C.p700;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!disabled }}
      onPress={disabled ? undefined : onPress}
      style={({ pressed }) => [
        st.btn,
        { backgroundColor: bg, opacity: pressed ? 0.8 : 1 },
        kind === 'ghost' && st.btnGhost,
        style,
      ]}
    >
      <Text style={{ fontSize: 17, fontWeight: '700', color: fg }}>{label}</Text>
    </Pressable>
  );
}

type Tone = 'danger' | 'caution' | 'info' | 'success';

const cardTone: Record<Tone, ViewStyle> = {
  danger: { borderColor: C.danger, backgroundColor: C.dangerBg },
  caution: { borderColor: C.warningBorder, backgroundColor: C.warningBg },
  info: { borderColor: C.p100, backgroundColor: C.infoBg },
  success: { borderColor: C.successBorder, backgroundColor: C.successBg },
};

export function Card({
  children,
  style,
  onPress,
  tone,
}: {
  children: ReactNode;
  style?: ViewStyle;
  onPress?: () => void;
  tone?: Tone;
}) {
  const body = <View style={[st.card, tone && cardTone[tone], style]}>{children}</View>;
  return onPress ? (
    <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => ({ opacity: pressed ? 0.85 : 1 })}>
      {body}
    </Pressable>
  ) : (
    body
  );
}

// 상태는 색만이 아니라 글자 라벨로 (NFR-024)
const chipTone = {
  danger: [C.dangerBg, C.danger],
  caution: [C.warningBg, C.warning],
  info: [C.infoBg, C.info],
  success: [C.successBg, C.success],
  neutral: [C.muted, C.text2],
  primary: [C.p600, C.onPrimary],
} as const;

export function Chip({ label, tone = 'neutral' }: { label: string; tone?: keyof typeof chipTone }) {
  const [bg, fg] = chipTone[tone];
  return (
    <View style={[st.chip, { backgroundColor: bg }]}>
      <Text style={{ fontSize: 13, fontWeight: '700', color: fg }}>{label}</Text>
    </View>
  );
}

export function Section({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <View style={{ marginTop: S.section }}>
      <View style={st.sectionHead}>
        <Text style={T.subhead} accessibilityRole="header">
          {title}
        </Text>
        {right}
      </View>
      <View style={{ gap: S.gap }}>{children}</View>
    </View>
  );
}

// 공통 화면 틀: 상단바(뒤로 · 제목) + 본문 + 아래 고정 버튼
export function Screen({
  title,
  children,
  back = true,
  footer,
  scroll = true,
  onBack,
}: {
  title: string;
  children: ReactNode;
  back?: boolean;
  footer?: ReactNode;
  scroll?: boolean;
  onBack?: () => void;
}) {
  const router = useRouter();
  const ins = useSafeAreaInsets();
  const canBack = back && (!!onBack || router.canGoBack());
  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <View style={[st.bar, { paddingTop: ins.top + 8 }]}>
        {canBack ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={copy.common.back}
            hitSlop={12}
            onPress={onBack ?? (() => router.back())}
            style={st.barSide}
          >
            <Text style={{ fontSize: 26, color: C.text }}>‹</Text>
          </Pressable>
        ) : (
          <View style={st.barSide} />
        )}
        <Text style={[T.subhead, { flex: 1 }]} numberOfLines={1} accessibilityRole="header">
          {title}
        </Text>
      </View>
      {scroll ? (
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ padding: S.side, paddingBottom: (footer ? 120 : S.section) + ins.bottom }}
        >
          {children}
        </ScrollView>
      ) : (
        <View style={{ flex: 1 }}>{children}</View>
      )}
      {footer ? <View style={[st.footer, { paddingBottom: ins.bottom + 12 }]}>{footer}</View> : null}
    </View>
  );
}

// 입력 칸 (CM-01 · CM-02 · CM-06 공통)
export function Field({
  label,
  value,
  onChangeText,
  placeholder,
  secure,
  helper,
  error,
  editable = true,
  keyboardType,
}: {
  label: string;
  value: string;
  onChangeText?: (v: string) => void;
  placeholder?: string;
  secure?: boolean;
  helper?: string;
  error?: string;
  editable?: boolean;
  keyboardType?: KeyboardTypeOptions;
}) {
  return (
    <View style={{ gap: 6 }}>
      <Text style={T.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={C.text3}
        secureTextEntry={secure}
        editable={editable}
        autoCapitalize="none"
        keyboardType={keyboardType}
        style={[
          st.input,
          {
            borderColor: error ? C.danger : C.borderStrong,
            backgroundColor: editable ? C.card : C.muted,
            color: editable ? C.text : C.text2,
          },
        ]}
      />
      {error ? (
        <Text style={{ fontSize: 14, color: C.danger }}>※ {error}</Text>
      ) : helper ? (
        <Text style={T.caption}>{helper}</Text>
      ) : null}
    </View>
  );
}

export function Radio({ on, label, onPress }: { on: boolean; label: string; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ checked: on }}
      onPress={onPress}
      style={[st.row, { minHeight: L.touch, paddingRight: 16 }]}
    >
      <Text style={{ fontSize: 18, color: on ? C.p600 : C.text3 }}>{on ? '●' : '○'}</Text>
      <Text style={T.body}>{label}</Text>
    </Pressable>
  );
}

export function Check({
  on,
  label,
  onPress,
  right,
  bold,
}: {
  on: boolean;
  label: string;
  onPress: () => void;
  right?: ReactNode;
  bold?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked: on }}
      onPress={onPress}
      style={[st.row, { minHeight: L.touch }]}
    >
      <View style={[st.box, { borderColor: on ? C.p600 : C.borderStrong, backgroundColor: on ? C.p600 : C.card }]}>
        {on && <Text style={{ color: C.onPrimary, fontSize: 14, fontWeight: '800' }}>✓</Text>}
      </View>
      <Text style={[bold ? T.bodyM : T.body, { flex: 1 }]}>{label}</Text>
      {right}
    </Pressable>
  );
}

// 확인 창 (CM-04-E1 · MY-S1-E1 등)
export function Confirm({
  visible,
  title,
  body,
  ok,
  onOk,
  onCancel,
  danger = true,
}: {
  visible: boolean;
  title: string;
  body: string;
  ok: string;
  onOk: () => void;
  onCancel: () => void;
  danger?: boolean;
}) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={st.dim}>
        <View style={[st.card, { gap: 10 }]} accessibilityViewIsModal>
          <Text style={T.heading} accessibilityRole="header">
            {title}
          </Text>
          <Text style={[T.body, { color: C.text2 }]}>{body}</Text>
          <Btn label={ok} kind={danger ? 'danger' : 'primary'} onPress={onOk} style={{ marginTop: 8 }} />
          <Btn label={copy.common.cancel} kind="secondary" onPress={onCancel} />
        </View>
      </View>
    </Modal>
  );
}

export function Disclaimer() {
  return <Text style={[T.caption, { textAlign: 'center', marginTop: 20 }]}>{copy.common.disclaimer}</Text>;
}

const st = StyleSheet.create({
  btn: {
    minHeight: L.button,
    borderRadius: R.control,
    paddingHorizontal: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnGhost: { minHeight: L.touch },
  card: { backgroundColor: C.card, borderRadius: R.card, padding: 16, borderWidth: 1, borderColor: C.border },
  chip: { borderRadius: R.chip, paddingHorizontal: 10, paddingVertical: 4, alignSelf: 'flex-start' },
  sectionHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingBottom: 12,
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  barSide: { width: 28 },
  footer: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    padding: 16,
    backgroundColor: C.card,
    borderTopWidth: 1,
    borderTopColor: C.border,
  },
  input: { borderWidth: 1, borderRadius: R.control, padding: 14, fontSize: 16 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  box: { width: 22, height: 22, borderRadius: 6, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  dim: { flex: 1, backgroundColor: C.dim, justifyContent: 'center', padding: 28 },
});
