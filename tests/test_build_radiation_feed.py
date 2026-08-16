import unittest
from datetime import datetime, timedelta, timezone

from scripts.build_radiation_feed import CPM_PER_USVH, build, classify, region_of

NOW = datetime(2026, 8, 16, 5, 0, 0, tzinfo=timezone.utc)


def device(cpm=38.0, lat=37.36, lon=140.37, age_days=0, key="lnd_7318c", **extra):
    captured = (NOW - timedelta(days=age_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {"loc_lat": lat, "loc_lon": lon, "when_captured": captured,
           "device_sn": "test-sensor", "device_class": "geigiecast"}
    if key:
        row[key] = cpm
    row.update(extra)
    return row


class RadiationFeedTests(unittest.TestCase):
    def test_dose_bands_use_natural_background_as_the_baseline(self):
        self.assertEqual(classify(0.12), ("Green", "평상 수준"))
        self.assertEqual(classify(0.50), ("Orange", "주의 관찰"))
        self.assertEqual(classify(2.97), ("Red", "높음"))

    def test_cpm_converts_with_the_documented_lnd7318_factor(self):
        incident = build([device(cpm=334.0)], now=NOW)[0]

        self.assertEqual(CPM_PER_USVH, 334.0)
        self.assertEqual(incident["dose"], 1.0)
        self.assertEqual(incident["severity"], 100.0)

    def test_tubes_with_a_different_conversion_factor_are_excluded(self):
        # 환산계수가 다른 관이 섞이면 μSv/h 비교 자체가 무의미해진다
        self.assertEqual(build([device(key="lnd_712u")], now=NOW), [])

    def test_stale_and_future_readings_are_dropped(self):
        self.assertEqual(build([device(age_days=30)], now=NOW), [])
        self.assertEqual(build([device(age_days=-5)], now=NOW), [])
        self.assertEqual(len(build([device(age_days=3)], now=NOW)), 1)

    def test_device_without_coordinates_or_reading_is_dropped(self):
        self.assertEqual(build([device(lat=None)], now=NOW), [])
        self.assertEqual(build([device(key=None)], now=NOW), [])
        self.assertEqual(build([device(cpm=0)], now=NOW), [])

    def test_region_is_derived_from_coordinates(self):
        self.assertEqual(region_of(37.5, 127.0), "동아시아")
        self.assertEqual(region_of(51.4, 30.0), "유럽")
        self.assertEqual(region_of(40.7, -74.0), "북미")
        self.assertEqual(region_of(-85.0, 0.0), "기타 지역")

    def test_results_are_ranked_by_dose(self):
        incidents = build([device(cpm=40), device(cpm=900, lat=51.4, lon=30.0)], now=NOW)

        self.assertEqual([round(i["dose"], 2) for i in incidents],
                         sorted([round(i["dose"], 2) for i in incidents], reverse=True))

    def test_incident_carries_the_shared_monitor_contract(self):
        incident = build([device()], now=NOW)[0]

        for key in ("lat", "lon", "name", "country", "dateadded", "threat", "tags", "severity", "reportUrl"):
            self.assertIn(key, incident)
        self.assertRegex(incident["dateadded"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
        self.assertIn("μSv/h", incident["threat"])


if __name__ == "__main__":
    unittest.main()
