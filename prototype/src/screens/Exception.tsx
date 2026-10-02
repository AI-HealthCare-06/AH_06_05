import React from 'react';
import { Linking, Text, View } from 'react-native';
import { useApp } from '../store';
import { C, T } from '../theme';
import { Btn, Card, Chip, Note, Screen } from '../ui';

// Figma 04 OCR · 02 공통 예외 화면 문구 그대로
type E = { id: string; title: string; chip?: [string, any]; icon?: string; head: string; body: string; reason?: string; primary: string; secondary?: string; foot?: string; note?: string };
const E: Record<string, E> = {
  quality: { id: 'OC-01-E1', title: '촬영 품질 확인', chip: ['화질 낮음', 'caution'], head: '사진이 흐리거나 어두워요', body: '빛이 충분한 곳에서 문서 전체가 보이도록 다시 촬영해 주세요.', reason: '2번째 사진 — 초점 흐림 · 조명 부족 · 문서 일부 잘림', primary: '다시 촬영하기', secondary: '그래도 계속 진행하기', foot: '※ 인식이 잘 안 될 수 있어요. 결과 화면에서 꼭 확인해 주세요.', note: 'API: O-5 결과 failedFiles[].code = IMAGE_QUALITY_LOW, fileIndex = 2' },
  camera: { id: 'OC-01-E2', title: '카메라 접근 권한 필요', icon: '!', head: '카메라를 사용할 수 없어요', body: '카메라 권한이 꺼져 있거나 카메라를 열 수 없어요. 설정에서 권한을 허용하거나 갤러리에서 사진을 올려 주세요.', primary: '설정으로 이동', secondary: '갤러리에서 계속하기', foot: '※ 카메라 없이도 갤러리 업로드로 기능을 계속 이용할 수 있어요.', note: '처음엔 OS 권한 팝업 → 거부하면 이 화면 (안건 #7 권한 안내 방식 통일)' },
  notdoc: { id: 'OC-01-E3', title: '문서를 찾지 못했어요', icon: '?', head: '문서를 찾지 못했어요', body: '사진에서 처방전이나 약봉투를 확인할 수 없어요. 문서가 화면 전체에 나오도록 다시 촬영해 주세요.', reason: '문서 형태를 인식하지 못함 (예: 인물 · 사물 사진, 빈 화면)', primary: '다시 촬영하기', secondary: '갤러리에서 다시 선택', note: 'API: O-5 결과 NOT_A_DOCUMENT' },
  ocrfail: { id: 'OC-02-E1', title: '직접 입력하기', icon: '?', head: '글자를 인식하지 못했어요', body: '사진이 잘 안 나왔거나 손글씨 처방전일 수 있어요. 약 이름을 직접 입력해 주세요.', primary: '약 이름 검색', secondary: '다시 촬영하기', foot: '입력하면 비슷한 약 이름을 추천해 드려요', note: '직접 입력한 약은 붙일 처방전이 없어 API 결정 필요 (안건 #12)' },
  network: { id: 'CM-08', title: '', icon: '!', head: '인터넷 연결이 불안정해요', body: '연결 상태를 확인하고 다시 시도해 주세요.', primary: '다시 시도', secondary: '홈으로' },
  nocam: { id: 'OC-01-E4 (안)', title: '기본 카메라 확인', chip: ['안내', 'info'], head: '기본 카메라를 열 수 없어요', body: '휴대폰의 기본 카메라 앱을 찾지 못했어요. 갤러리에서 처방전 사진을 골라 주세요.', primary: '갤러리에서 선택', note: '안건 #10 수정안: 시스템 카메라를 직접 지정해서 열고, 못 찾을 때만 이 화면 (Figma에는 아직 없음)' },
};

export default function Exception({ kind }: { kind: string }) {
  const { back, go, toTab } = useApp();
  const e = E[kind] || E.quality;
  const act = (label: string) => {
    if (label === '설정으로 이동') Linking.openSettings();
    else if (label === '약 이름 검색') go('recognize', { search: true });
    else if (label === '홈으로') toTab('home');
    else back();
  };
  return (
    <Screen id={e.id} title={e.title} agendaKey="capture"
      footer={<View style={{ gap: 8 }}>
        <Btn label={e.primary} onPress={() => act(e.primary)} />
        {e.secondary && <Btn label={e.secondary} kind="secondary" onPress={() => act(e.secondary!)} />}
      </View>}>
      <Card style={{ alignItems: e.icon ? 'center' : 'flex-start', gap: 10, marginTop: 8 }}>
        {e.icon && <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: C.muted, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 26, fontWeight: '800', color: C.text2 }}>{e.icon}</Text></View>}
        {e.chip && <Chip label={e.chip[0]} tone={e.chip[1]} />}
        <Text style={[T.heading, e.icon && { textAlign: 'center' }]}>{e.head}</Text>
        <Text style={[T.body, { color: C.text2 }, e.icon && { textAlign: 'center' }]}>{e.body}</Text>
      </Card>
      {e.reason && (
        <Card style={{ marginTop: 12 }}>
          <Text style={T.small}>감지된 사유</Text>
          <Text style={[T.body, { marginTop: 4 }]}>{e.reason}</Text>
        </Card>
      )}
      {e.foot && <Text style={[T.caption, { marginTop: 12 }]}>{e.foot}</Text>}
      {e.note && <Note>{e.note}</Note>}
    </Screen>
  );
}
