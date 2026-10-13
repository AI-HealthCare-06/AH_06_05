// 촬영에서 결과까지 이어지는 흐름의 값 (찍은 사진, 처방전 번호, 분석 번호)
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

type Flow = {
  photos: string[];
  setPhotos: (v: string[] | ((p: string[]) => string[])) => void;
  prescriptionIds: number[];
  setPrescriptionIds: (v: number[]) => void;
  analysisId: number | null;
  setAnalysisId: (v: number | null) => void;
  reset: () => void;
};

const Ctx = createContext<Flow | null>(null);

export function useFlow() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useFlow는 FlowProvider 안에서만 쓸 수 있어요');
  return v;
}

export function FlowProvider({ children }: { children: ReactNode }) {
  const [photos, setPhotos] = useState<string[]>([]);
  const [prescriptionIds, setPrescriptionIds] = useState<number[]>([]);
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const reset = useCallback(() => {
    setPhotos([]);
    setPrescriptionIds([]);
    setAnalysisId(null);
  }, []);
  const value = useMemo(
    () => ({ photos, setPhotos, prescriptionIds, setPrescriptionIds, analysisId, setAnalysisId, reset }),
    [photos, prescriptionIds, analysisId, reset],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
