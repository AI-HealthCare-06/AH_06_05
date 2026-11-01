// 약 이름에 붙은 "(수출명: 돌로린정)", "(수출용)" 같은 수출용 표시는 화면에서 뺀다 (서버가 보내는 이름은 그대로).
// 괄호 ( ) 나 대괄호 [ ] 안에 있으면 그 묶음 전체를 빼고 (안에 괄호가 또 있어도 짝을 맞춤),
// 괄호 없이 뒤에 붙어 있으면 "수출" 앞까지만 남긴다.
const EXPORT = /수출(명|용)/;
const OPEN = '([';
const CLOSE = ')]';

function balanced(s: string): boolean {
  let depth = 0;
  for (const ch of s) {
    if (OPEN.includes(ch)) depth++;
    else if (CLOSE.includes(ch)) depth--;
    if (depth < 0) return false;
  }
  return depth === 0;
}

export function drugLabel(name: string): string {
  let out = name;
  for (let guard = 0; guard < 5; guard++) {
    const m = EXPORT.exec(out);
    if (!m) break;
    const i = m.index;
    // 수출 표시가 들어 있는 가장 가까운 여는 괄호를 찾는다
    let open = -1;
    let depth = 0;
    for (let k = i - 1; k >= 0; k--) {
      const ch = out[k];
      if (CLOSE.includes(ch)) depth++;
      else if (OPEN.includes(ch)) {
        if (depth === 0) {
          open = k;
          break;
        }
        depth--;
      }
    }
    if (open < 0) {
      out = out.slice(0, i).trim();
      continue;
    }
    let end = out.length;
    depth = 0;
    for (let k = open; k < out.length; k++) {
      const ch = out[k];
      if (OPEN.includes(ch)) depth++;
      else if (CLOSE.includes(ch)) {
        depth--;
        if (depth === 0) {
          end = k + 1;
          break;
        }
      }
    }
    out = (out.slice(0, open) + out.slice(end)).trim();
  }
  // 원래 데이터에 괄호가 짝이 안 맞는 이름("...mg))", "...그램[")은 짝이 맞을 때까지 뒤의 괄호를 덜어 냄
  while (!balanced(out) && /[()[\]]$/.test(out)) out = out.slice(0, -1).trim();
  return out;
}
