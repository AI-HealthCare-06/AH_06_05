import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { ActivityIndicator, Image, Linking, Modal, Pressable, Text, View } from 'react-native';

import { getOcrJob, SAMPLE_PHOTO, uploadPrescriptions } from '@/features/ocr/api';
import { useFlow } from '@/features/ocr/flow';
import { ApiError, USE_MOCK } from '@/shared/api/client';
import { copy } from '@/shared/copy';
import { C, T } from '@/shared/theme';
import { Btn, Card, Chip, Screen, Section } from '@/shared/ui';

const MAX = 5;
type Problem = { kind: 'quality' | 'notDocument' | 'ocrFailed' | 'camera'; fileIndex?: number; canContinue?: boolean };

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

// OC-01 촬영 · 업로드, OC-01-E1 화질 낮음, OC-01-E2 카메라 권한, OC-01-E3 문서 아님, OC-02-E1 인식 실패
export default function Capture() {
  const router = useRouter();
  const { photos, setPhotos, setPrescriptionIds, setDuplicates } = useFlow();
  const [reading, setReading] = useState(false);
  const [tips, setTips] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [netError, setNetError] = useState<string | null>(null);
  const busy = useRef(false);
  const left = MAX - photos.length;

  const add = (uris: string[]) => setPhotos((p) => [...p, ...uris].slice(0, MAX));

  const shoot = async () => {
    setProblem(null);
    try {
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) return setProblem({ kind: 'camera' });
      const r = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.6 });
      if (!r.canceled) add(r.assets.map((a) => a.uri));
    } catch {
      setProblem({ kind: 'camera' });
    }
  };

  const pick = async () => {
    setProblem(null);
    const r = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: true,
      selectionLimit: Math.max(left, 1),
      quality: 0.6,
    });
    if (!r.canceled) add(r.assets.map((a) => a.uri));
  };

  // O-1 업로드 후 O-5를 1초마다 확인
  const start = async () => {
    if (busy.current) return;
    busy.current = true;
    setProblem(null);
    setNetError(null);
    setReading(true);
    try {
      const { jobId } = await uploadPrescriptions(photos);
      for (let i = 0; i < 60; i += 1) {
        await wait(1000);
        const job = await getOcrJob(jobId);
        if (job.status === 'queued' || job.status === 'running') continue;
        const bad = job.failedFiles[0];
        setDuplicates((job.duplicatedFiles ?? []).map((d) => d.fileIndex));
        if (job.status === 'failed') return setProblem({ kind: 'ocrFailed' });
        if (bad && job.prescriptionIds.length === 0) {
          return setProblem({ kind: bad.code === 'NOT_A_DOCUMENT' ? 'notDocument' : 'quality', fileIndex: bad.fileIndex });
        }
        if (bad) {
          setPrescriptionIds(job.prescriptionIds);
          return setProblem({ kind: 'quality', fileIndex: bad.fileIndex, canContinue: true });
        }
        setPrescriptionIds(job.prescriptionIds);
        return router.replace('/recognize');
      }
      setNetError(copy.common.serverError);
    } catch (e) {
      if (e instanceof ApiError && e.code === 'FILE_TOO_LARGE') setNetError(e.message);
      else setNetError(e instanceof ApiError ? e.message : copy.common.serverError);
    } finally {
      busy.current = false;
      setReading(false);
    }
  };

  if (problem) return <ProblemView problem={problem} onRetake={() => { setPhotos([]); setProblem(null); }} onGallery={pick} onContinue={() => router.replace('/recognize')} onBack={() => router.back()} />;

  return (
    <Screen
      title={copy.capture.title}
      footer={<Btn label={photos.length ? copy.capture.start(photos.length) : copy.capture.startEmpty} disabled={!photos.length || reading} onPress={start} />}
    >
      <Text style={T.heading}>{copy.capture.head}</Text>
      <Text style={[T.body, { color: C.text2, marginTop: 4, marginBottom: 16 }]}>{copy.capture.body}</Text>
      <Card tone="info">
        <Text style={T.bodyM}>{copy.capture.guideTitle}</Text>
        <Text style={[T.caption, { color: C.text, marginTop: 4 }]}>{copy.capture.guideBody}</Text>
      </Card>

      <View style={{ flexDirection: 'row', gap: 10, marginTop: 16 }}>
        <Btn label={copy.capture.shoot} onPress={shoot} disabled={!left} style={{ flex: 1 }} />
        <Btn label={copy.capture.pick} kind="secondary" onPress={pick} disabled={!left} style={{ flex: 1 }} />
      </View>

      <Section
        title={copy.capture.photos(photos.length, MAX)}
        right={
          photos.length ? (
            <Pressable accessibilityRole="button" hitSlop={8} onPress={() => setPhotos([])}>
              <Text style={[T.bodyM, { color: C.p700 }]}>{copy.capture.clear}</Text>
            </Pressable>
          ) : undefined
        }
      >
        {photos.length === 0 ? (
          <Card>
            <Text style={T.caption}>{copy.capture.empty}</Text>
            {USE_MOCK && <Btn label={copy.capture.sample} kind="ghost" onPress={() => add([SAMPLE_PHOTO, SAMPLE_PHOTO])} style={{ marginTop: 6 }} />}
          </Card>
        ) : (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
            {photos.map((u, i) => (
              <View key={`${u}-${i}`} style={{ width: 96 }}>
                {u === SAMPLE_PHOTO ? (
                  <View style={{ width: 96, height: 120, borderRadius: 10, backgroundColor: C.muted, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: C.border }}>
                    <Text style={T.small}>샘플</Text>
                  </View>
                ) : (
                  <Image accessibilityLabel={`${i + 1}번째 사진`} source={{ uri: u }} style={{ width: 96, height: 120, borderRadius: 10 }} />
                )}
                <Text style={[T.small, { marginTop: 4 }]}>{i + 1}</Text>
              </View>
            ))}
          </View>
        )}
        <Text style={T.caption}>{copy.capture.sameOnce}</Text>
        <Pressable accessibilityRole="button" hitSlop={8} onPress={() => setTips(true)}>
          <Text style={[T.bodyM, { color: C.p700 }]}>{copy.capture.tips}</Text>
        </Pressable>
      </Section>

      {netError && <Text style={[T.body, { color: C.danger, marginTop: 16 }]}>※ {netError}</Text>}

      <Modal visible={tips} transparent animationType="slide" onRequestClose={() => setTips(false)}>
        <Pressable style={{ flex: 1, backgroundColor: C.dim }} onPress={() => setTips(false)} />
        <View style={{ backgroundColor: C.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, gap: 10 }}>
          <Text style={T.heading}>{copy.capture.tipsTitle}</Text>
          {copy.capture.tipList.map((t) => (
            <Text key={t} style={T.body}>
              · {t}
            </Text>
          ))}
          <Btn label={copy.capture.close} kind="secondary" onPress={() => setTips(false)} />
        </View>
      </Modal>

      <Modal visible={reading} transparent animationType="fade">
        <View style={{ flex: 1, backgroundColor: C.dim, alignItems: 'center', justifyContent: 'center' }}>
          <Card style={{ width: 280, alignItems: 'center', gap: 12 }}>
            <ActivityIndicator size="large" color={C.p600} />
            <Text style={T.subhead}>{copy.capture.reading}</Text>
            <Text style={T.caption}>{copy.capture.readingSub}</Text>
          </Card>
        </View>
      </Modal>
    </Screen>
  );
}

function ProblemView({ problem, onRetake, onGallery, onContinue, onBack }: { problem: Problem; onRetake: () => void; onGallery: () => void; onContinue: () => void; onBack: () => void }) {
  const e = copy.captureError;
  const c = problem.kind === 'quality' ? e.quality : problem.kind === 'camera' ? e.camera : problem.kind === 'notDocument' ? e.notDocument : e.ocrFailed;
  const foot = 'foot' in c ? c.foot : null;
  const primary = () => (problem.kind === 'camera' ? Linking.openSettings() : onRetake());
  const secondary = () => (problem.kind === 'camera' ? onGallery() : problem.kind === 'quality' ? (problem.canContinue ? onContinue() : onRetake()) : problem.kind === 'ocrFailed' ? onBack() : onGallery());
  return (
    <Screen
      title={c.title}
      onBack={onBack}
      footer={
        <View style={{ gap: 8 }}>
          <Btn label={c.primary} onPress={primary} />
          <Btn label={c.secondary} kind="secondary" onPress={secondary} />
        </View>
      }
    >
      <Card style={{ gap: 10, marginTop: 8 }}>
        {problem.kind === 'quality' && <Chip label={e.quality.chip} tone="caution" />}
        <Text style={T.heading}>{c.head}</Text>
        <Text style={[T.body, { color: C.text2 }]}>{c.body}</Text>
      </Card>
      {problem.fileIndex !== undefined && (
        <Card style={{ marginTop: 12 }}>
          <Text style={T.small}>{e.reason}</Text>
          <Text style={[T.body, { marginTop: 4 }]}>{e.fileIndex(problem.fileIndex)}</Text>
        </Card>
      )}
      {foot && <Text style={[T.caption, { marginTop: 12 }]}>{foot}</Text>}
    </Screen>
  );
}
