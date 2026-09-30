import React, { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View, ViewStyle } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { agendaFor } from './agenda';
import { useApp } from './store';
import { C, R, S, T } from './theme';

export function Btn({ label, onPress, kind = 'primary', disabled, style }: { label: string; onPress?: () => void; kind?: 'primary' | 'secondary' | 'ghost' | 'danger'; disabled?: boolean; style?: ViewStyle }) {
  const bg = disabled ? C.muted : kind === 'primary' ? C.p600 : kind === 'danger' ? C.danger : kind === 'secondary' ? C.p50 : 'transparent';
  const fg = disabled ? C.text3 : kind === 'primary' || kind === 'danger' ? C.onPrimary : C.p700;
  return (
    <Pressable onPress={disabled ? undefined : onPress} style={({ pressed }) => [{ backgroundColor: bg, borderRadius: R.control, paddingVertical: 16, alignItems: 'center', opacity: pressed ? 0.8 : 1 }, kind === 'ghost' && { paddingVertical: 10 }, style]}>
      <Text style={{ fontSize: 17, fontWeight: '700', color: fg }}>{label}</Text>
    </Pressable>
  );
}

export function Card({ children, style, onPress, tone }: { children: React.ReactNode; style?: ViewStyle; onPress?: () => void; tone?: 'danger' | 'caution' | 'info' | 'success' | 'anno' }) {
  const toneStyle = tone === 'danger' ? { borderColor: C.danger, backgroundColor: C.dangerBg } : tone === 'caution' ? { borderColor: '#F5C77E', backgroundColor: C.warningBg } : tone === 'info' ? { borderColor: C.p100, backgroundColor: C.infoBg } : tone === 'success' ? { borderColor: '#A7E3C8', backgroundColor: C.successBg } : tone === 'anno' ? { borderColor: C.annoBorder, backgroundColor: C.annoBg } : {};
  const body = <View style={[st.card, toneStyle, style]}>{children}</View>;
  return onPress ? <Pressable onPress={onPress} style={({ pressed }) => ({ opacity: pressed ? 0.85 : 1 })}>{body}</Pressable> : body;
}

// 상태는 색만이 아니라 글자 라벨로 (NFR-024)
export function Chip({ label, tone = 'neutral' }: { label: string; tone?: 'danger' | 'caution' | 'info' | 'success' | 'neutral' | 'primary' }) {
  const m = { danger: [C.dangerBg, C.danger], caution: [C.warningBg, C.warning], info: [C.infoBg, C.info], success: [C.successBg, C.success], neutral: [C.muted, C.text2], primary: [C.p600, C.onPrimary] }[tone];
  return <View style={{ backgroundColor: m[0], borderRadius: R.chip, paddingHorizontal: 10, paddingVertical: 4, alignSelf: 'flex-start' }}><Text style={{ fontSize: 13, fontWeight: '700', color: m[1] }}>{label}</Text></View>;
}

export function Section({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <View style={{ marginTop: S.section }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <Text style={T.subhead}>{title}</Text>
        {right}
      </View>
      <View style={{ gap: S.gap }}>{children}</View>
    </View>
  );
}

// 공통 화면 틀: 상단바 + 화면 ID + 안건 버튼
export function Screen({ id, title, agendaKey, children, back = true, footer, scroll = true, onBack }: { id: string; title: string; agendaKey?: string; children: React.ReactNode; back?: boolean; footer?: React.ReactNode; scroll?: boolean; onBack?: () => void }) {
  const { s, back: goBack, stack } = useApp();
  const ins = useSafeAreaInsets();
  const [open, setOpen] = useState(false);
  const items = agendaKey ? agendaFor(agendaKey) : [];
  const canBack = back && stack.length > 0;
  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <View style={[st.bar, { paddingTop: ins.top + 8 }]}>
        {canBack ? <Pressable hitSlop={12} onPress={onBack || goBack}><Text style={{ fontSize: 26, color: C.text, width: 28 }}>‹</Text></Pressable> : <View style={{ width: 28 }} />}
        <Text style={[T.subhead, { flex: 1, textAlign: canBack ? 'left' : 'left' }]} numberOfLines={1}>{title}</Text>
        {s.showIds && <View style={st.idBadge}><Text style={{ fontSize: 11, fontWeight: '700', color: C.annoText }}>{id}</Text></View>}
      </View>
      {scroll ? <ScrollView contentContainerStyle={{ padding: S.side, paddingBottom: 140 }}>{children}</ScrollView> : <View style={{ flex: 1 }}>{children}</View>}
      {footer && <View style={[st.footer, { paddingBottom: 12 }]}>{footer}</View>}
      {items.length > 0 && (
        <Pressable onPress={() => setOpen(true)} style={[st.fab, { bottom: footer ? 96 : scroll ? 20 : 84 }]}>
          <Text style={{ color: C.annoText, fontWeight: '800', fontSize: 14 }}>안건 {items.length}</Text>
        </Pressable>
      )}
      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <Pressable style={st.dim} onPress={() => setOpen(false)} />
        <View style={[st.sheet, { paddingBottom: ins.bottom + 16 }]}>
          <Text style={[T.heading, { marginBottom: 4 }]}>이 화면에서 정할 것</Text>
          <Text style={[T.caption, { marginBottom: 12 }]}>{id} · 9/28 오후 미팅 안건</Text>
          <ScrollView style={{ maxHeight: 420 }} contentContainerStyle={{ gap: 10 }}>
            {items.map((a) => (
              <Card key={a.no} tone="anno">
                <Text style={[T.label, { color: C.annoText }]}>#{a.no} {a.title}</Text>
                <Text style={[T.caption, { marginTop: 4, color: C.text }]}>{a.body}</Text>
                <Text style={[T.small, { marginTop: 6 }]}>확인: {a.who}</Text>
              </Card>
            ))}
          </ScrollView>
          <Btn label="닫기" kind="secondary" onPress={() => setOpen(false)} style={{ marginTop: 12 }} />
        </View>
      </Modal>
    </View>
  );
}

export function Note({ children }: { children: React.ReactNode }) {
  return (
    <View style={{ backgroundColor: C.annoBg, borderColor: C.annoBorder, borderWidth: 1, borderRadius: 10, padding: 10, marginTop: 12 }}>
      <Text style={{ fontSize: 13, color: C.annoText, lineHeight: 19 }}>프로토타입 · {children}</Text>
    </View>
  );
}

export const st = StyleSheet.create({
  card: { backgroundColor: C.card, borderRadius: R.card, padding: 16, borderWidth: 1, borderColor: C.border },
  bar: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingBottom: 12, backgroundColor: C.card, borderBottomWidth: 1, borderBottomColor: C.border },
  idBadge: { backgroundColor: C.annoBg, borderColor: C.annoBorder, borderWidth: 1, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  footer: { position: 'absolute', left: 0, right: 0, bottom: 0, padding: 16, backgroundColor: C.card, borderTopWidth: 1, borderTopColor: C.border },
  fab: { position: 'absolute', right: 16, backgroundColor: C.annoBg, borderColor: C.annoBorder, borderWidth: 1.5, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 10, shadowColor: '#000', shadowOpacity: 0.12, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 3 },
  dim: { flex: 1, backgroundColor: 'rgba(15,23,42,0.35)' },
  sheet: { backgroundColor: C.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
});

// 입력 칸 (CM-01 · CM-02 · CM-06 공통)
import { TextInput as RNTextInput } from 'react-native';
export function Field({ label, value, onChangeText, placeholder, secure, helper, error, editable = true, keyboardType }: { label: string; value: string; onChangeText?: (v: string) => void; placeholder?: string; secure?: boolean; helper?: string; error?: string; editable?: boolean; keyboardType?: any }) {
  return (
    <View style={{ gap: 6 }}>
      <Text style={T.label}>{label}</Text>
      <RNTextInput value={value} onChangeText={onChangeText} placeholder={placeholder} placeholderTextColor={C.text3} secureTextEntry={secure} editable={editable} autoCapitalize="none" keyboardType={keyboardType}
        style={{ borderWidth: 1, borderColor: error ? C.danger : C.borderStrong, borderRadius: R.control, padding: 14, fontSize: 16, backgroundColor: editable ? C.card : C.muted, color: editable ? C.text : C.text2 }} />
      {error ? <Text style={{ fontSize: 14, color: C.danger }}>※ {error}</Text> : helper ? <Text style={T.caption}>{helper}</Text> : null}
    </View>
  );
}

export function Radio({ on, label, onPress }: { on: boolean; label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, paddingRight: 16 }}>
      <Text style={{ fontSize: 18, color: on ? C.p600 : C.text3 }}>{on ? '●' : '○'}</Text>
      <Text style={T.body}>{label}</Text>
    </Pressable>
  );
}

export function Check({ on, label, onPress, right, bold }: { on: boolean; label: string; onPress: () => void; right?: React.ReactNode; bold?: boolean }) {
  return (
    <Pressable onPress={onPress} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 }}>
      <View style={{ width: 22, height: 22, borderRadius: 6, borderWidth: 1.5, borderColor: on ? C.p600 : C.borderStrong, backgroundColor: on ? C.p600 : C.card, alignItems: 'center', justifyContent: 'center' }}>
        {on && <Text style={{ color: '#fff', fontSize: 14, fontWeight: '800' }}>✓</Text>}
      </View>
      <Text style={[bold ? T.bodyM : T.body, { flex: 1 }]}>{label}</Text>
      {right}
    </Pressable>
  );
}

// 확인 창 (CM-04-E1 · MY-S1-E1 등)
export function Confirm({ visible, title, body, ok, onOk, onCancel, danger = true }: { visible: boolean; title: string; body: string; ok: string; onOk: () => void; onCancel: () => void; danger?: boolean }) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={{ flex: 1, backgroundColor: 'rgba(15,23,42,0.45)', justifyContent: 'center', padding: 28 }}>
        <View style={[st.card, { gap: 10 }]}>
          <Text style={T.heading}>{title}</Text>
          <Text style={[T.body, { color: C.text2 }]}>{body}</Text>
          <Btn label={ok} kind={danger ? 'danger' : 'primary'} onPress={onOk} style={{ marginTop: 8 }} />
          <Btn label="취소" kind="secondary" onPress={onCancel} />
        </View>
      </View>
    </Modal>
  );
}

export function Disclaimer() {
  return <Text style={[T.caption, { textAlign: 'center', marginTop: 20 }]}>의학적 진단 · 처방이 아닌 참고용 안내예요</Text>;
}
