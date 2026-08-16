import unittest

from scripts.build_spaceweather_feed import (
    MAX_MARKERS, build, normalize_longitude, probability_label, storm_level, thin_grid,
)


def ovation(coordinates, observed="2026-08-16T05:15:00Z"):
    return {"Observation Time": observed, "Data Format": "[Longitude, Latitude, Aurora]",
            "coordinates": coordinates}


class SpaceWeatherFeedTests(unittest.TestCase):
    def test_colour_comes_from_kp_not_from_local_probability(self):
        # 조용한 날에도 극지 확률은 30%대까지 오른다. 확률로 색을 매기면 평시에도 전부 주의색이 된다.
        quiet, _ = storm_level(1.33)
        storm, _ = storm_level(6.0)
        severe, _ = storm_level(8.5)

        self.assertEqual(quiet, "Green")
        self.assertEqual(storm, "Orange")
        self.assertEqual(severe, "Red")

    def test_storm_labels_follow_the_noaa_g_scale(self):
        self.assertEqual(storm_level(4.9)[1], "폭풍 없음")
        self.assertEqual(storm_level(5.0)[1], "G1 약한 폭풍")
        self.assertEqual(storm_level(9.5)[1], "G5 극심한 폭풍")

    def test_unknown_kp_degrades_to_green(self):
        self.assertEqual(storm_level(None), ("Green", "Kp 미상"))

    def test_probability_label_describes_local_intensity(self):
        self.assertEqual(probability_label(5), "약함")
        self.assertEqual(probability_label(20), "보통")
        self.assertEqual(probability_label(45), "강함")
        self.assertEqual(probability_label(80), "매우 강함")

    def test_longitude_is_moved_from_0_360_into_minus180_180(self):
        self.assertEqual(normalize_longitude(10), 10)
        self.assertEqual(normalize_longitude(200), -160)
        self.assertEqual(normalize_longitude(359), -1)

    def test_thin_grid_keeps_the_strongest_point_per_cell(self):
        # 같은 셀에 들어가는 두 점이면 큰 값만 남아야 한다
        points = [[0, 60, 5], [1, 61, 9], [100, -70, 12]]

        thinned = thin_grid(points)

        self.assertIn(9, [p[2] for p in thinned])
        self.assertNotIn(5, [p[2] for p in thinned])
        self.assertEqual(len(thinned), 2)

    def test_thin_grid_drops_points_below_the_noise_floor(self):
        self.assertEqual(thin_grid([[0, 60, 0], [4, 62, 1]]), [])

    def test_thin_grid_respects_the_marker_cap(self):
        points = [[lon, lat, 10] for lon in range(0, 360, 8) for lat in range(-88, 88, 5)]

        self.assertLessEqual(len(thin_grid(points)), MAX_MARKERS)

    def test_build_splits_hemispheres_and_keeps_probability_as_severity(self):
        incidents, kp, storm = build(ovation([[10, 65, 30], [10, -65, 20]]), 2.0)

        by_name = {i["country"]: i for i in incidents}
        self.assertEqual(set(by_name), {"북반구 오로라대", "남반구 오로라대"})
        self.assertEqual(by_name["북반구 오로라대"]["severity"], 30.0)
        self.assertEqual(kp, 2.0)
        self.assertEqual(storm, "폭풍 없음")

    def test_incident_carries_the_shared_monitor_contract(self):
        incidents, _kp, _storm = build(ovation([[10, 65, 30]]), 2.0)
        incident = incidents[0]

        for key in ("lat", "lon", "name", "country", "dateadded", "threat", "tags", "severity", "reportUrl"):
            self.assertIn(key, incident)
        self.assertEqual(incident["dateadded"], "2026-08-16T05:15:00")
        self.assertIn(incident["tags"], ("Green", "Orange", "Red"))


if __name__ == "__main__":
    unittest.main()
