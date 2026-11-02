// 사진 첨부 고르기 (CB-04, 설계 메모 4-9). 사진은 긴 변 1600px 안팎 JPEG로 줄이고(HEIC도 JPEG로 바뀜), 위치 정보(EXIF)는 담지 않음. PDF는 줄이지 않음
import * as DocumentPicker from 'expo-document-picker';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import * as ImagePicker from 'expo-image-picker';

export const MAX_BYTES = 10 * 1024 * 1024; // 서버(O-1)와 같음
const MAX_SIDE = 1600;

export type Picked = { uri: string; name: string; type: 'image/jpeg' | 'application/pdf'; pdf: boolean };
// null은 사용자가 고르지 않고 닫음
export type PickResult = { file: Picked } | { error: 'permission' | 'tooBig' | 'type' | 'fail' } | null;

async function shrink(uri: string): Promise<Picked> {
  let ref = await ImageManipulator.manipulate(uri).renderAsync(); // 줄이지 않아도 거치게 해 HEIC를 JPEG로 바꿈
  if (Math.max(ref.width, ref.height) > MAX_SIDE) {
    const long = ref.width >= ref.height ? { width: MAX_SIDE } : { height: MAX_SIDE };
    ref = await ImageManipulator.manipulate(uri).resize(long).renderAsync();
  }
  const out = await ref.saveAsync({ format: SaveFormat.JPEG, compress: 0.8 });
  return { uri: out.uri, name: 'photo.jpg', type: 'image/jpeg', pdf: false };
}

async function fromImage(asset: ImagePicker.ImagePickerAsset): Promise<PickResult> {
  if (asset.fileSize && asset.fileSize > MAX_BYTES * 3) return { error: 'tooBig' }; // 줄이기 전이라 넉넉히
  try {
    return { file: await shrink(asset.uri) };
  } catch {
    return { error: 'fail' };
  }
}

export async function takePhoto(): Promise<PickResult> {
  const perm = await ImagePicker.requestCameraPermissionsAsync();
  if (!perm.granted) return { error: 'permission' };
  const r = await ImagePicker.launchCameraAsync({ quality: 1, exif: false });
  return r.canceled || !r.assets[0] ? null : fromImage(r.assets[0]);
}

// 시스템 사진 선택기라 권한 요청이 없음
export async function pickPhoto(): Promise<PickResult> {
  const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 1, exif: false });
  return r.canceled || !r.assets[0] ? null : fromImage(r.assets[0]);
}

export async function pickFile(): Promise<PickResult> {
  const r = await DocumentPicker.getDocumentAsync({
    type: ['image/jpeg', 'image/png', 'application/pdf'],
    copyToCacheDirectory: true,
  });
  const a = r.canceled ? null : r.assets[0];
  if (!a) return null;
  if (a.size && a.size > MAX_BYTES) return { error: 'tooBig' };
  if (a.mimeType === 'application/pdf') return { file: { uri: a.uri, name: 'file.pdf', type: 'application/pdf', pdf: true } };
  if (!a.mimeType?.startsWith('image/')) return { error: 'type' };
  try {
    return { file: await shrink(a.uri) };
  } catch {
    return { error: 'fail' };
  }
}
