from datetime import date

from tortoise.contrib.test import TestCase
from tortoise.exceptions import IntegrityError

from app.models.masters import Disease, DrugProduct
from app.models.ocr import (
    DocType,
    MatchStatus,
    OcrJob,
    OcrJobStatus,
    Prescription,
    PrescriptionDisease,
    PrescriptionItem,
    PrescriptionItemCandidate,
)
from app.models.users import Gender, User


async def make_user(email: str) -> User:
    return await User.create(
        email=email,
        hashed_password="x",
        name="테스터",
        gender=Gender.FEMALE,
        birthday=date(1950, 1, 1),
        phone_number="01000000000",
    )


async def make_prescription(user: User) -> Prescription:
    job = await OcrJob.create(user=user, file_count=1)
    return await Prescription.create(user=user, ocr_job=job, file_index=0, doc_type=DocType.PRESCRIPTION)


class TestOcrModels(TestCase):
    async def test_job_to_items_with_candidates(self):
        user = await make_user("ocr1@example.com")
        drug = await DrugProduct.create(edi_code="641900040", item_name="노바스크정5밀리그램", route="내복")
        other = await DrugProduct.create(edi_code="641900041", item_name="노바크정", route="내복")
        await Disease.create(code="I10", name_kr="본태성(일차성) 고혈압")
        rx = await make_prescription(user)
        await PrescriptionDisease.create(prescription=rx, disease_id="I10", is_main=True)
        item = await PrescriptionItem.create(
            prescription=rx,
            drug=drug,
            raw_name="노바스크정5밀리그람",
            match_score=0.91,
            match_status=MatchStatus.NEEDS_CONFIRM,
            dose_per_time=1,
            times_per_day=1,
            total_days=30,
        )
        await PrescriptionItemCandidate.create(item=item, rank=1, drug=drug, score=0.91)
        await PrescriptionItemCandidate.create(item=item, rank=2, drug=other, score=0.85)

        job = await OcrJob.get(id=rx.ocr_job_id)
        assert job.status == OcrJobStatus.QUEUED
        loaded = await PrescriptionItem.get(id=item.id).prefetch_related("candidates")
        assert loaded.drug_id == "641900040"  # 칸 이름은 edi_code
        assert [c.rank for c in sorted(loaded.candidates, key=lambda c: c.rank)] == [1, 2]
        assert (await PrescriptionDisease.get(prescription=rx)).disease_id == "I10"

    async def test_unmatched_item_has_no_drug(self):
        user = await make_user("ocr2@example.com")
        rx = await make_prescription(user)
        item = await PrescriptionItem.create(prescription=rx, raw_name="알수없는약", match_status=MatchStatus.UNMATCHED)
        assert item.drug_id is None

    async def test_candidate_rank_is_unique_per_item(self):
        user = await make_user("ocr3@example.com")
        drug = await DrugProduct.create(edi_code="641900050", item_name="테스트정")
        rx = await make_prescription(user)
        item = await PrescriptionItem.create(
            prescription=rx, raw_name="테스트정", match_status=MatchStatus.AUTO, drug=drug
        )
        await PrescriptionItemCandidate.create(item=item, rank=1, drug=drug)
        with self.assertRaises(IntegrityError):
            await PrescriptionItemCandidate.create(item=item, rank=1, drug=drug)

    async def test_deleting_user_removes_prescriptions(self):
        # 탈퇴 = 전부 즉시 삭제 (REQ-004)
        user = await make_user("ocr4@example.com")
        rx = await make_prescription(user)
        await PrescriptionItem.create(prescription=rx, raw_name="약", match_status=MatchStatus.UNMATCHED)
        await user.delete()
        assert await Prescription.filter(id=rx.id).count() == 0
        assert await PrescriptionItem.filter(prescription_id=rx.id).count() == 0
        assert await OcrJob.filter(id=rx.ocr_job_id).count() == 0
