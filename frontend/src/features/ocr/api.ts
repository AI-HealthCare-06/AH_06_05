// OCR API 호출 (O-1 ~ O-5). 화면은 이 함수들만 부름
import { File } from 'expo-file-system';
import { Platform } from 'react-native';

import { api } from '@/shared/api/client';

import type { DrugSearch, ItemPatch, OcrJob, Prescription } from './types';

export const SAMPLE_PHOTO = 'sample'; // 가짜 응답 확인용 자리표시 (사진 대신)

async function toFormData(uris: string[]): Promise<FormData> {
  const form = new FormData();
  for (const [i, uri] of uris.entries()) {
    if (uri === SAMPLE_PHOTO) continue;
    if (Platform.OS === 'web') {
      form.append('files', await (await fetch(uri)).blob(), `photo${i + 1}.jpg`);
    } else {
      // Expo의 fetch는 {uri, name, type} 모양을 보낼 수 없어서(Unsupported FormDataPart) File 객체로 붙임
      form.append('files', new File(uri) as unknown as Blob, `photo${i + 1}.jpg`);
    }
  }
  return form;
}

// O-1 업로드 (최대 5장). OCR은 작업으로 돌리고 O-5로 확인
export async function uploadPrescriptions(uris: string[]) {
  return api<{ jobId: number; status: 'queued' }>('POST', '/prescriptions', await toFormData(uris));
}

// O-5 작업 상태 (1초 간격 폴링)
export const getOcrJob = (jobId: number) => api<OcrJob>('GET', `/ocr-jobs/${jobId}`);

// O-2 인식 결과
export const getPrescription = (id: number) => api<Prescription>('GET', `/prescriptions/${id}`);

// O-3 약 고르기, 수정, 빼기
export const patchItem = (prescriptionId: number, itemId: number, body: ItemPatch & Record<string, unknown>) =>
  api<void>('PATCH', `/prescriptions/${prescriptionId}/items/${itemId}`, body);

// O-4 약 이름 검색
export const searchDrugs = (q: string, size = 5) =>
  api<DrugSearch>('GET', `/drugs/search?q=${encodeURIComponent(q)}&size=${size}`);
