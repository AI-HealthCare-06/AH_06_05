// 공통 부품 — 프로토타입 ui.tsx에서 가져옴 (안건 버튼 · 화면 ID 표시 · 프로토타입 메모는 뺌)
import { useRouter } from 'expo-router';
import { useState, type ReactNode, type Ref } from 'react';
import {
  KeyboardTypeOptions,
  Modal,
  Pressable,
  ScrollView,
  StyleProp,
  StyleSheet,
  Text,
  TextStyle,
  TextInput,
  View,
  ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { copy } from '@/shared/copy';
import { C, L, R, S, T } from '@/shared/theme';
import { BackIcon } from '@/shared/ui/icons';

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

// 목록 한 줄: 앞에 짧은 줄(-)을 붙이고, 줄이 길어져도 둘째 줄이 글자 시작 위치에 맞음
export function Bullet({ text, textStyle = T.body }: { text: string; textStyle?: StyleProp<TextStyle> }) {
  return (
    <View style={{ flexDirection: 'row', gap: 8 }}>
      <Text style={textStyle}>-</Text>
      <Text style={[textStyle, { flex: 1 }]}>{text}</Text>
    </View>
  );
}

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
  fab = false,
  onBack,
  right,
  scrollRef,
}: {
  title: string;
  children: ReactNode;
  back?: boolean;
  footer?: ReactNode;
  scroll?: boolean;
  fab?: boolean; // 챗봇 버튼이 떠 있는 탭 화면: 맨 아래 내용이 버튼에 가려지지 않게 여백을 둠
  onBack?: () => void;
  right?: ReactNode; // 제목 줄 오른쪽 버튼
  scrollRef?: Ref<ScrollView>; // 화면 안에서 원하는 위치로 스크롤해야 할 때
}) {
  const router = useRouter();
  const ins = useSafeAreaInsets();
  const canBack = back && (!!onBack || router.canGoBack());
  // 하단 고정 영역은 화면 위에 떠 있으므로 실제 높이를 재서 스크롤 아래 여백으로 씀 (버튼 둘과 안내 두 줄처럼 높으면 마지막 카드가 가려졌음)
  const [footerH, setFooterH] = useState(0);
  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <View style={[st.bar, { paddingTop: ins.top }]}>
        <View style={st.barRow}>
          {canBack ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={copy.common.back}
              hitSlop={12}
              onPress={onBack ?? (() => router.back())}
              style={st.barBack}
            >
              <BackIcon />
            </Pressable>
          ) : null}
          <Text style={st.barTitle} numberOfLines={1} accessibilityRole="header">
            {title}
          </Text>
          {right}
        </View>
      </View>
      {scroll ? (
        <ScrollView
          ref={scrollRef}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{
            padding: S.side,
            paddingBottom: fab ? L.fab + L.fabGap * 2 : footer ? Math.max(footerH, 120 + ins.bottom) + S.section : S.section + ins.bottom,
          }}
        >
          {children}
        </ScrollView>
      ) : (
        <View style={{ flex: 1 }}>{children}</View>
      )}
      {footer ? (
        <View
          style={[st.footer, { paddingBottom: ins.bottom + 12 }]}
          onLayout={(e) => setFooterH(Math.ceil(e.nativeEvent.layout.height))}
        >
          {footer}
        </View>
      ) : null}
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
  content,
}: {
  visible: boolean;
  title: string;
  body: string;
  ok: string;
  onOk: () => void;
  onCancel: () => void;
  danger?: boolean;
  content?: ReactNode; // 본문 대신 그릴 것 (동의 요약과 전체 내용 접기)
}) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={st.dim}>
        <View style={[st.card, { gap: 10 }]} accessibilityViewIsModal>
          <Text style={T.heading} accessibilityRole="header">
            {title}
          </Text>
          {content ?? <Text style={[T.body, { color: C.text2 }]}>{body}</Text>}
          <Btn label={ok} kind={danger ? 'danger' : 'primary'} onPress={onOk} style={{ marginTop: 8 }} />
          <Btn label={copy.common.cancel} kind="secondary" onPress={onCancel} />
        </View>
      </View>
    </Modal>
  );
}

// 알림 창: 확인 버튼 하나만 있는 안내 (Confirm은 취소 버튼이 항상 있음)
export function Notice({ visible, title, body, ok, onOk }: { visible: boolean; title: string; body: string; ok: string; onOk: () => void }) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onOk}>
      <View style={st.dim}>
        <View style={[st.card, { gap: 10 }]} accessibilityViewIsModal>
          <Text style={T.heading} accessibilityRole="header">
            {title}
          </Text>
          <Text style={[T.body, { color: C.text2 }]}>{body}</Text>
          <Btn label={ok} onPress={onOk} style={{ marginTop: 8 }} />
        </View>
      </View>
    </Modal>
  );
}

// 동의 글: 핵심 요약 몇 줄을 먼저 보이고 법정 전체 문구는 [전체 내용 보기]로 접음 (11/2 멘토 피드백 "모달 글이 너무 많음").
// 전체 문구는 지우지 않고 그대로 보여 줄 수 있어야 함
export function ConsentText({ summary, full }: { summary: readonly string[]; full: string }) {
  const [open, setOpen] = useState(false);
  return (
    <View style={{ gap: 6 }}>
      {summary.map((line) => (
        <Bullet key={line} text={line} textStyle={[T.body, { color: C.text2 }]} />
      ))}
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen((v) => !v)}
        style={{ minHeight: L.touch, justifyContent: 'center' }}
      >
        <Text style={{ fontSize: 15, fontWeight: '700', color: C.p700 }}>{open ? copy.common.fullClose : copy.common.fullOpen}</Text>
      </Pressable>
      {open && <Text style={T.caption}>{full}</Text>}
    </View>
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
  // 위쪽 제목 줄: 높이 L.header, 좌우 여백 S.side (본문, 홈 로고와 같은 선). 뒤로 가기가 없으면 제목이 그 선에서 바로 시작
  bar: { backgroundColor: C.card, borderBottomWidth: 1, borderBottomColor: C.border },
  barRow: { height: L.header, flexDirection: 'row', alignItems: 'center', paddingHorizontal: S.side },
  barBack: { width: 28, height: L.touch, justifyContent: 'center', alignItems: 'flex-start', marginLeft: -9 },
  barTitle: { flex: 1, fontSize: 17, fontWeight: '800', color: C.text },
  footer: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: S.side,
    paddingTop: 12,
    backgroundColor: C.card,
    borderTopWidth: 1,
    borderTopColor: C.border,
  },
  input: { borderWidth: 1, borderRadius: R.control, padding: 14, fontSize: 16 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  box: { width: 22, height: 22, borderRadius: 6, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  dim: { flex: 1, backgroundColor: C.dim, justifyContent: 'center', padding: 28 },
});
