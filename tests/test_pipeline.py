import unittest

from src.territory_pipeline import (
    TerritoryAssignment,
    ZipRecord,
    infer_prospective_owner,
    normalize_zip,
    select_active_owner,
)
from src.territory_pipeline import RepActivity  # imported separately for clarity


def make_assignment(
    zip_code: str, lat: float, lng: float, email: str, deal_count: int
) -> TerritoryAssignment:
    return TerritoryAssignment(
        zip=zip_code,
        lat=lat,
        lng=lng,
        city="TestCity",
        state_id="TS",
        state_name="Test State",
        county_name="Test County",
        owner_email=email,
        owner_name="Owner " + email,
        owner_status="ACTIVE",
        deal_count=deal_count,
        prospective_owner_email=None,
        prospective_owner_name=None,
        inference_reason=None,
    )


class PipelineTests(unittest.TestCase):
    def test_normalize_zip(self) -> None:
        self.assertEqual(normalize_zip("123"), "00123")
        self.assertEqual(normalize_zip("60601-1234"), "60601")
        self.assertIsNone(normalize_zip(""))

    def test_select_active_owner_prefers_highest_deal_count(self) -> None:
        activity = [
            RepActivity(
                zip="12345",
                state="TS",
                owner_name="A",
                owner_email="a@example.com",
                deal_count=5,
                status="ACTIVE",
            ),
            RepActivity(
                zip="12345",
                state="TS",
                owner_name="B",
                owner_email="b@example.com",
                deal_count=10,
                status="ACTIVE",
            ),
        ]
        selected = select_active_owner(activity)
        self.assertEqual(selected["12345"].owner_email, "b@example.com")

    def test_infer_prospective_owner_prefers_magnitude_and_dominance(self) -> None:
        target = ZipRecord(
            zip="00000",
            lat=0.0,
            lng=0.0,
            city="Target",
            state_id="TS",
            state_name="Test State",
            county_name="Target County",
            population=None,
            timezone="UTC",
        )
        # Neighbor A is closer but weaker; Neighbor B is slightly farther with more deals.
        neighbors = [
            make_assignment("11111", lat=0.1, lng=0.0, email="close@example.com", deal_count=5),
            make_assignment("22222", lat=0.15, lng=0.0, email="strong@example.com", deal_count=25),
        ]
        email, name, reason = infer_prospective_owner(
            target, neighbors, radius_miles=500, max_neighbors=5
        )
        self.assertEqual(email, "strong@example.com")
        self.assertIn("mag=", reason or "")


if __name__ == "__main__":
    unittest.main()
