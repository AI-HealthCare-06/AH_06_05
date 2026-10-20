// 건강 정보 (API 명세서 v1.5 초안 A-1 health, U-1 health, U-2 health, #101). 서버 app/models/users.py와 같게
// 흡연과 음주 값은 국민건강영양조사 문항(BS3_1, BD1_11)에 "잘 모르겠어요"(unknown)를 더한 것
export const SMOKING = ['daily', 'sometimes', 'past', 'never', 'unknown'] as const;
export const DRINKING = ['none', 'lt_monthly', 'monthly', '2_4_monthly', '2_3_weekly', '4plus_weekly', 'unknown'] as const;
export const DIALYSIS = ['yes', 'no', 'unknown'] as const;
// 생활습관 팩트표 질환 id (lifestyle_diseases.id)
export const DISEASE_IDS = ['HTN', 'DM2', 'DLP', 'CKD', 'IHD', 'STROKE', 'AF', 'COPD', 'OP', 'OA'] as const;
export const EXAM_NAME_MAX = 50;

export type Smoking = (typeof SMOKING)[number];
export type Drinking = (typeof DRINKING)[number];
export type Dialysis = (typeof DIALYSIS)[number];
export type DiseaseId = (typeof DISEASE_IDS)[number];
export type UpcomingExam = { name: string; date: string }; // date는 YYYY-MM-DD

export type Health = {
  smoking: Smoking;
  drinking: Drinking;
  diseases: DiseaseId[];
  pregnant: 'yes' | 'no' | null; // 여성만
  dialysis: Dialysis | null;
  heightCm: number | null;
  weightKg: number | null;
  upcomingExams: UpcomingExam[];
};

// U-2: 바꿀 칸만 보냄. 목록 칸은 보낸 목록으로 통째로 바뀜
export type HealthUpdate = Partial<Health>;
