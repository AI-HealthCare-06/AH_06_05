import * as ImagePicker from 'expo-image-picker';
import React, { useState } from 'react';
import { ActivityIndicator, Image, Modal, Pressable, Text, View } from 'react-native';
import { useApp } from '../store';
import { C, T } from '../theme';
import { Btn, Card, Chip, Note, Screen, Section } from '../ui';

const MAX = 5;

export default function Capture() {
  const { s, set, go, replace, loadSample } = useApp();
  const [reading, setReading] = useState<null | number>(null);
  const [tips, setTips] = useState(false);
  const photos = s.photos;
  const left = MAX - photos.length;

  const add = (uris: string[]) => set({ photos: [...photos, ...uris].slice(0, MAX) });

  const shoot = async () => {
    try {
      const p = await ImagePicker.requestCameraPermissionsAsync();
      if (!p.granted) return go('exception', { kind: 'camera' });
      const r = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.6 });
      if (!r.canceled) add(r.assets.map((a) => a.uri));
    } catch {
      add(['sample']);
    }
  };
  const pick = async () => {
    try {
      const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsMultipleSelection: true, selectionLimit: left, quality: 0.6 });
      if (!r.canceled) add(r.assets.map((a) => a.uri));
    } catch {
      add(['sample']);
    }
  };

  const start = () => {
    // O-1 202 + jobId → O-5 폴링 흉내
    setReading(1);
    setTimeout(() => setReading(2), 900);
    setTimeout(() => {
      setReading(null);
      loadSample();
      replace('recognize');
    }, 1900);
  };

  return (
    <Screen id="OC-01" title="진료기록 촬영 · 업로드" agendaKey="capture"
      footer={<Btn label={photos.length ? `${photos.length}장 인식 시작하기` : '사진을 먼저 추가해 주세요'} disabled={!photos.length} onPress={start} />}>
      <Text style={T.heading}>처방전 또는 약봉투를 찍어 주세요</Text>
      <Text style={[T.body, { color: C.text2, marginTop: 4, marginBottom: 16 }]}>병원이 여러 곳이면 처방전을 모두 찍어 주세요. 최대 5장까지 이어서 찍을 수 있어요.</Text>
      <Card tone="info">
        <Text style={T.bodyM}>휴대폰 카메라로 찍어요</Text>
        <Text style={[T.caption, { color: C.text, marginTop: 4 }]}>[촬영하기]를 누르면 휴대폰 카메라가 열려요.{'\n'}찍은 사진은 사진첩에 저장되지 않고,{'\n'}인식이 끝나면 바로 지워져요.</Text>
      </Card>

      <View style={{ flexDirection: 'row', gap: 10, marginTop: 16 }}>
        <Btn label="촬영하기" onPress={shoot} disabled={!left} style={{ flex: 1 }} />
        <Btn label="갤러리에서 선택" kind="secondary" onPress={pick} disabled={!left} style={{ flex: 1 }} />
      </View>

      <Section title={`찍은 사진  ${photos.length} / ${MAX}장`} right={photos.length ? <Pressable onPress={() => set({ photos: [] })}><Text style={{ color: C.p700, fontWeight: '600' }}>모두 지우기</Text></Pressable> : undefined}>
        {photos.length === 0 ? (
          <Card>
            <Text style={T.caption}>여러 병원 처방전 · 약봉투를 최대 5장까지 한 번에 점검할 수 있어요.</Text>
            <Btn label="샘플 처방전 2장으로 해 보기" kind="ghost" onPress={() => add(['sample', 'sample'])} style={{ marginTop: 6 }} />
          </Card>
        ) : (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
            {photos.map((u, i) => (
              <View key={i} style={{ width: 96 }}>
                {u === 'sample' ? (
                  <View style={{ width: 96, height: 120, borderRadius: 10, backgroundColor: C.muted, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: C.border }}>
                    <Text style={{ fontSize: 30 }}>🧾</Text><Text style={T.small}>샘플</Text>
                  </View>
                ) : (
                  <Image source={{ uri: u }} style={{ width: 96, height: 120, borderRadius: 10 }} />
                )}
                <Text style={[T.small, { marginTop: 4 }]}>{i + 1}  {u === 'sample' ? (i === 0 ? '○○내과' : i === 1 ? '△△의원' : '샘플') : ''}</Text>
              </View>
            ))}
          </View>
        )}
        <Text style={T.caption}>여러 병원 처방전을 한 번에 점검할 수 있어요.</Text>
        <Text style={T.caption}>같은 처방전은 한 번만 찍어 주세요.</Text>
        <Pressable onPress={() => setTips(true)}><Text style={{ color: C.p700, fontWeight: '600' }}>촬영 팁 보기 {'>'}</Text></Pressable>
      </Section>

      <Section title="예외 화면 미리 보기">
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {[['quality', '화질 낮음 E1'], ['camera', '카메라 권한 E2'], ['notdoc', '문서 아님 E3'], ['ocrfail', '글자 인식 실패 OC-02-E1'], ['network', '공통 오류 CM-08'], ['nocam', '기본 카메라 못 엶 E4(안)']].map(([k, l]) => (
            <Pressable key={k} onPress={() => go('exception', { kind: k })}><Chip label={l} tone="neutral" /></Pressable>
          ))}
        </View>
      </Section>
      <Note>OCR은 아직 연결 전이라, 어떤 사진을 올려도 샘플 처방전 2장(내과 4종 + 이비인후과 2종) 인식 결과가 나와요. 약 이름 · 성분 · 안전성 점검은 실제 공공데이터예요.</Note>

      <Modal visible={tips} transparent animationType="slide" onRequestClose={() => setTips(false)}>
        <Pressable style={{ flex: 1, backgroundColor: 'rgba(15,23,42,0.35)' }} onPress={() => setTips(false)} />
        <View style={{ backgroundColor: C.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, gap: 10 }}>
          <Text style={T.heading}>촬영 팁</Text>
          {['밝은 곳에서 그림자 없이 찍어 주세요', '처방전 네 모서리가 모두 나오게 찍어 주세요', '글자가 흐리면 조금 떨어져서 다시 찍어 주세요', '약봉투는 약 이름이 적힌 면을 찍어 주세요'].map((t) => <Text key={t} style={T.body}>· {t}</Text>)}
          <Btn label="닫기" kind="secondary" onPress={() => setTips(false)} />
        </View>
      </Modal>
      <Modal visible={reading !== null} transparent animationType="fade">
        <View style={{ flex: 1, backgroundColor: 'rgba(15,23,42,0.45)', alignItems: 'center', justifyContent: 'center' }}>
          <Card style={{ width: 280, alignItems: 'center', gap: 12 }}>
            <ActivityIndicator size="large" color={C.p600} />
            <Text style={T.subhead}>처방전을 읽고 있어요</Text>
            <Text style={T.caption}>{reading} / {Math.max(photos.length, 1)}장 · 잠시만 기다려 주세요</Text>
          </Card>
        </View>
      </Modal>
    </Screen>
  );
}
