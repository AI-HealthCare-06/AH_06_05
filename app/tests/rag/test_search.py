"""근거 검색 전체 흐름 시험. OpenAI는 같은 모양의 가짜로 바꿔서, 실제 DB(pgvector, pg_trgm)에서 돌린다"""

import json
import tempfile
from pathlib import Path
from typing import Any

from tortoise.contrib.test import TestCase

from app.models.rag import EMBEDDING_DIM, EvidenceChunk
from app.services.rag import loader, prompts
from app.services.rag.llm import LLMError
from app.services.rag.pipeline import search

DRUG = "100000001"
OTHER = "100000002"


def vec(weights: dict[int, float]) -> list[float]:
    out = [0.0] * EMBEDDING_DIM
    for i, w in weights.items():
        out[i] = w
    return out


def row(
    cid: str,
    n: int,
    *,
    kind: str = "drug",
    drug: str | None = DRUG,
    disease: str | None = None,
    group: str | None = None,
    raw: str | None = None,
    embedding: list[float] | None = None,
) -> dict[str, Any]:
    return {
        "id": cid,
        "kind": kind,
        "drug": drug,
        "disease": disease,
        "letter": "S" if kind == "drug" else None,
        "group": group or cid,
        "order": n,
        "ctx": "제목" if kind == "drug" else "",
        "raw": raw or f"zzz{n:03d} text",
        "embed_text": f"embed {cid}",
        "drug_name": "시험약" if drug else None,
        "embedding": embedding if embedding is not None else vec({n % EMBEDDING_DIM: 1.0}),
        "source_order": n,
    }


class FakeLLM:
    """프롬프트 머리말로 어느 단계인지 가려 정해진 답을 돌려준다. 단계별 호출 수와 받은 글을 남긴다"""

    def __init__(
        self,
        picks: list[int] | None = None,
        a: str = "ENOUGH",
        b: str = "ENOUGH",
        direct: bool = True,
        c: str = "FULL",
        rewrite: str = "다시 쓴 질문 zzz",
        question_vec: list[float] | None = None,
        rewrite_vec: list[float] | None = None,
    ) -> None:
        self.picks = [1] if picks is None else picks
        self.answers = {
            prompts.JUDGE_A_PROMPT: json.dumps({"verdict": a}),
            prompts.JUDGE_B_PROMPT: json.dumps({"verdict": b, "direct": direct}),
            prompts.ANSWER_PROMPT: json.dumps({"type": c}),
        }
        self.rewrite = rewrite
        self.vectors = [question_vec or vec({0: 1.0}), rewrite_vec or vec({1: 1.0})]
        self.calls: list[str] = []
        self.select_prompt = ""
        self.fail_on: str | None = None

    async def complete(self, prompt: str) -> str:
        for head, answer in self.answers.items():
            if prompt.startswith(head):
                self.calls.append("judge")
                return answer
        if prompt.startswith(prompts.REWRITE_PROMPT):
            self.calls.append("rewrite")
            if self.fail_on == "rewrite":
                raise LLMError("재작성 실패")
            return self.rewrite
        if prompt.startswith(prompts.SELECT_PROMPT):
            self.calls.append("select")
            self.select_prompt = prompt
            if self.fail_on == "select":
                raise LLMError("고르기 실패")
            return json.dumps({"ids": self.picks})
        raise AssertionError("알 수 없는 프롬프트")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append("embed")
        assert len(texts) == 2
        return self.vectors


class NoCallLLM:
    async def complete(self, prompt: str) -> str:
        raise AssertionError("OpenAI를 부르면 안 됩니다")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("OpenAI를 부르면 안 됩니다")


class SearchTest(TestCase):
    async def test_no_code_does_not_call_openai(self) -> None:
        result = await search("아무 질문", [], [], llm=NoCallLLM())
        assert result.reason == "no_code" and result.evidence == []

    async def test_no_candidate(self) -> None:
        await loader.load_rows([row("D:1:S1", 1)])
        result = await search("질문", ["999999999"], [], llm=NoCallLLM())
        assert result.reason == "no_candidate"

    async def test_small_scope_sends_everything_as_candidates(self) -> None:
        await loader.load_rows([row(f"D:1:S{n}", n) for n in range(1, 41)] + [row("D:2:S1", 1, drug=OTHER)])
        llm = FakeLLM(picks=[2])
        result = await search("질문 zzz", [DRUG], [], llm=llm)
        assert result.reason is None
        assert [e.sentence_id for e in result.evidence] == ["D:1:S2"]
        assert "[40]" in llm.select_prompt and "[41]" not in llm.select_prompt  # 다른 약 글은 후보에 없음
        assert result.evidence[0].source == "drug_permit" and result.evidence[0].drug_code == DRUG
        assert result.rewritten == "다시 쓴 질문 zzz"

    async def test_large_scope_uses_union_of_four_rankings(self) -> None:
        rows = [
            row(f"D:1:S{n}", n, embedding=vec({n: 1.0}), raw=f"qqq{n:03d} aaa") for n in range(100)
        ]  # n번째 글은 n번째 축 방향의 벡터
        await loader.load_rows(rows)
        question_vec = vec({j: 1.0 / (1 + j) for j in range(100)})  # 앞 번호가 가까움 -> 0..29
        rewrite_vec = vec({j: 1.0 / (1 + (99 - j)) for j in range(100)})  # 뒤 번호가 가까움 -> 70..99
        llm = FakeLLM(picks=[1], question_vec=question_vec, rewrite_vec=rewrite_vec)
        result = await search("xxxxxxxx", [DRUG], [], llm=llm)  # 글자가 안 겹치면 글자 순위는 조각 순서(0..29)
        assert result.reason is None
        shown = llm.select_prompt.count("\n[")
        assert shown == 60  # 0..29와 70..99
        assert "[60]" in llm.select_prompt and "[61]" not in llm.select_prompt
        assert result.evidence[0].sentence_id == "D:1:S0"  # 첫 후보는 질문 임베딩 1위
        assert llm.select_prompt.index("qqq000") < llm.select_prompt.index("qqq099")

    async def test_pick_cap_is_eight(self) -> None:
        await loader.load_rows([row(f"D:1:S{n}", n) for n in range(1, 21)])
        llm = FakeLLM(picks=list(range(1, 15)))
        result = await search("질문", [DRUG], [], llm=llm)
        assert len(result.evidence) == 8

    async def test_no_selection(self) -> None:
        await loader.load_rows([row("D:1:S1", 1)])
        llm = FakeLLM(picks=[])
        result = await search("질문", [DRUG], [], llm=llm)
        assert result.reason == "no_selection" and "judge" not in llm.calls

    async def test_group_expansion_with_cap_and_first_sentence(self) -> None:
        rows = [row(f"D:1:S{n}", n, group="G1") for n in range(20)] + [row("D:1:S50", 50, group="G2")]
        await loader.load_rows(rows)
        llm = FakeLLM(picks=[16])  # 후보는 source_order 순서이므로 16번째 = S15
        result = await search("질문", [DRUG], [], llm=llm)
        ids = [e.sentence_id for e in result.evidence]
        assert len(ids) == 8 and ids[0] == "D:1:S0" and "D:1:S15" in ids

    async def test_fact_and_cross_scope_follow_disease(self) -> None:
        await loader.load_rows(
            [
                row("F:HTN:1", 1, kind="fact", drug=None, disease="HTN", raw="짠 음식 줄이기"),
                row("F:DM:1", 2, kind="fact", drug=None, disease="DM", raw="당 조절"),
                row("X:1", 3, kind="cross", drug=None, raw="겹칠 때 규칙"),
            ]
        )
        llm = FakeLLM(picks=[1, 2])
        result = await search("질문", [], ["HTN"], llm=llm)
        assert [e.sentence_id for e in result.evidence] == ["F:HTN:1", "X:1"]
        assert [e.source for e in result.evidence] == ["lifestyle_fact", "cross_rule"]
        assert "F:DM" not in llm.select_prompt and "당 조절" not in llm.select_prompt

    async def test_majority_decides(self) -> None:
        await loader.load_rows([row("D:1:S1", 1)])
        ok = await search("질문", [DRUG], [], llm=FakeLLM(a="PARTIAL", b="INSUFFICIENT", c="PARTIAL"))
        assert ok.reason is None and len(ok.evidence) == 1
        bad = await search("질문", [DRUG], [], llm=FakeLLM(a="ENOUGH", b="INSUFFICIENT", c="NONE"))
        assert bad.reason == "insufficient" and bad.evidence == []
        assert bad.verdicts is not None and bad.verdicts.passes == (True, False, False)

    async def test_risk_topic_blocked_without_two_full(self) -> None:
        await loader.load_rows([row("D:1:S1", 1)])
        blocked = await search(
            "약을 끊어도 되나요?", [DRUG], [], llm=FakeLLM(a="PARTIAL", b="PARTIAL", direct=False, c="FULL")
        )
        assert blocked.reason == "risk_blocked" and blocked.evidence == []
        passed = await search("약을 끊어도 되나요?", [DRUG], [], llm=FakeLLM())
        assert passed.reason is None and len(passed.evidence) == 1

    async def test_llm_error_returns_empty_with_reason(self) -> None:
        await loader.load_rows([row("D:1:S1", 1)])
        llm = FakeLLM()
        llm.fail_on = "select"
        result = await search("질문", [DRUG], [], llm=llm)
        assert result.reason == "llm_error" and result.evidence == []

    async def test_rewrite_failure_falls_back_to_question(self) -> None:
        await loader.load_rows([row("D:1:S1", 1)])
        llm = FakeLLM()
        llm.fail_on = "rewrite"
        result = await search("원래 질문", [DRUG], [], llm=llm)
        assert result.reason is None and result.rewritten == "원래 질문"

    async def test_duplicate_codes_are_merged(self) -> None:
        await loader.load_rows([row("D:1:S1", 1)])
        result = await search("질문", [DRUG, DRUG], [], llm=FakeLLM())
        assert [e.sentence_id for e in result.evidence] == ["D:1:S1"]


class LoaderTest(TestCase):
    async def test_load_is_idempotent_and_overwrites(self) -> None:
        r = row("D:1:S1", 1)
        assert await loader.load_rows([r]) == {"loaded": 1, "embedded": 0}
        r2 = {**r, "raw": "고친 글"}
        await loader.load_rows([r2])
        assert await EvidenceChunk.all().count() == 1
        saved = await EvidenceChunk.get(chunk_id="D:1:S1")
        assert saved.content == "고친 글" and saved.embedding_model == "text-embedding-3-small"

    async def test_missing_vectors_are_filled_by_llm(self) -> None:
        r = row("D:1:S1", 1)
        r["embedding"] = None
        counted: list[int] = []

        class Embedder:
            async def complete(self, prompt: str) -> str:
                raise AssertionError

            async def embed(self, texts: list[str]) -> list[list[float]]:
                counted.append(len(texts))
                return [vec({5: 1.0}) for _ in texts]

        assert await loader.load_rows([r], llm=Embedder()) == {"loaded": 1, "embedded": 1}
        assert counted == [1]
        assert (await EvidenceChunk.get(chunk_id="D:1:S1")).embedding is not None

    async def test_wrong_dimension_is_rejected(self) -> None:
        r = row("D:1:S1", 1, embedding=[0.1, 0.2])
        with self.assertRaises(ValueError):
            await loader.load_rows([r])

    async def test_read_rows_reads_lines_and_fills_source_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chunks.jsonl"
            first = {k: v for k, v in row("D:1:S1", 1).items() if k != "source_order"}
            path.write_text(json.dumps(first) + "\n\n" + json.dumps(row("D:1:S2", 2)), encoding="utf-8")
            rows = loader.read_rows(path)
        assert [r["id"] for r in rows] == ["D:1:S1", "D:1:S2"]
        assert rows[0]["source_order"] == 0  # 빈 줄 앞의 첫 줄은 줄 번호가 순서
