import unittest

from scripts.build_airquality_feed import CITIES, build_incident, classify

CITY = ("서울", "대한민국", 37.5665, 126.9780)


def block(aqi, **overrides):
    current = {
        "time": "2026-08-16T04:00",
        "european_aqi": aqi,
        "ozone": 121.0,
        "pm2_5": 14.3,
        "pm10": 15.0,
        "nitrogen_dioxide": 8.1,
        "sulphur_dioxide": 2.2,
        "carbon_monoxide": 190.0,
        "dust": 0.4,
        "uv_index": 6.2,
        "us_aqi": 55,
    }
    current.update(overrides)
    return {"current": current}


class AirQualityFeedTests(unittest.TestCase):
    def test_european_aqi_bands_fold_into_three_marker_colours(self):
        self.assertEqual(classify(10), ("Green", "좋음"))
        self.assertEqual(classify(30), ("Green", "양호"))
        self.assertEqual(classify(50), ("Orange", "보통"))
        self.assertEqual(classify(70), ("Orange", "나쁨"))
        self.assertEqual(classify(90), ("Red", "매우 나쁨"))
        self.assertEqual(classify(305), ("Red", "극히 나쁨"))

    def test_band_boundaries_belong_to_the_upper_band(self):
        self.assertEqual(classify(40)[1], "보통")
        self.assertEqual(classify(80)[1], "매우 나쁨")

    def test_build_incident_exposes_ozone_and_particulates(self):
        incident = build_incident(CITY, block(55))

        self.assertEqual(incident["ozone"], 121.0)
        self.assertEqual(incident["pm2_5"], 14.3)
        self.assertEqual(incident["pm10"], 15.0)
        self.assertEqual(incident["band"], "보통")
        self.assertEqual(incident["severity"], 55.0)

    def test_missing_pollutant_becomes_none_instead_of_zero(self):
        # 값 없음을 0으로 적으면 '오존 0' 이라는 거짓 측정치가 된다
        incident = build_incident(CITY, block(30, ozone=None))

        self.assertIsNone(incident["ozone"])

    def test_missing_aqi_drops_the_city(self):
        self.assertIsNone(build_incident(CITY, block(None)))
        self.assertIsNone(build_incident(CITY, {}))

    def test_short_timestamp_is_padded_to_full_iso_seconds(self):
        incident = build_incident(CITY, block(30))

        self.assertEqual(incident["dateadded"], "2026-08-16T04:00:00")

    def test_incident_carries_the_shared_monitor_contract(self):
        incident = build_incident(CITY, block(30))

        for key in ("lat", "lon", "name", "country", "dateadded", "threat", "tags", "severity", "reportUrl"):
            self.assertIn(key, incident)

    def test_city_table_has_korea_and_unique_valid_coordinates(self):
        self.assertGreaterEqual(sum(1 for c in CITIES if c[1] == "대한민국"), 10)
        self.assertEqual(len({(c[2], c[3]) for c in CITIES}), len(CITIES))
        for name, _country, lat, lon in CITIES:
            with self.subTest(city=name):
                self.assertTrue(-90 <= lat <= 90 and -180 <= lon <= 180)


if __name__ == "__main__":
    unittest.main()
