// 지난 기록 한 줄 (CM-04 목록, CM-03 홈 카드가 같이 씀) + 기록 열기
import { useRouter } from 'expo-router';
import { useCallback, type ReactNode } from 'react';
import { Pressable, Text, View } from 'react-native';

import { useFlow } from '@/features/ocr/flow';
import { copy } from '@/shared/copy';
import { C, T } from '@/shared/theme';
import { Card, Chip } from '@/shared/ui';

import type { AnalysisListItem } from './types';

const h = copy.history;

// 서버가 만든 라벨을 그대로 보여 주고, 색만 상태로 정함 (색만으로 알리지 않고 글자 라벨이 항상 있음)
export function labelTone(item: AnalysisListItem): 'danger' | 'caution' | 'info' | 'success' {
  if (item.status === 'running') return 'info';
  if (item.status === 'failed') return 'danger';
  return item.resultLabel.startsWith('확인 필요') ? 'caution' : 'success';
}

// 기록을 누르면: 끝난 분석은 결과 화면(RG-02~), 진행 중이거나 실패한 분석은 분석 화면(RG-01, RG-01-E1)으로
export function useOpenRecord() {
  const router = useRouter();
  const { setAnalysisId } = useFlow();
  return useCallback(
    (item: AnalysisListItem) => {
      setAnalysisId(item.analysisId);
      router.push(item.status === 'done' ? '/result' : '/analyzing');
    },
    [router, setAnalysisId],
  );
}

export function RecordCard({ item, onPress, right }: { item: AnalysisListItem; onPress: () => void; right?: ReactNode }) {
  const day = h.day(new Date(item.createdAt));
  const lines = [
    item.hospitals && item.hospitals.length > 0 ? item.hospitals.join(', ') : null,
    item.drugCount !== undefined ? h.drugs(item.drugCount) : null,
    item.diseaseNames && item.diseaseNames.length > 0 ? item.diseaseNames.join(', ') : null,
  ].filter((v): v is string => v !== null);
  return (
    <Card>
      {/* 누르는 영역과 삭제 버튼을 나눠서, 화면 읽기 도구가 두 가지를 따로 읽게 함 */}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${day}, ${item.resultLabel}. ${h.open}`}
        onPress={onPress}
        style={({ pressed }) => ({ gap: 6, opacity: pressed ? 0.85 : 1 })}
      >
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <Text style={T.subhead}>{day}</Text>
          <Chip label={item.resultLabel} tone={labelTone(item)} />
        </View>
        {lines.map((t) => (
          <Text key={t} style={[T.body, { color: C.text2 }]}>
            {t}
          </Text>
        ))}
      </Pressable>
      {right}
    </Card>
  );
}
