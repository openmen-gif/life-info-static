import unittest

from scripts.build_volcano_feed import classify_gvp, korean_status, parse_gvp, parse_title


RSS = b'''<?xml version="1.0"?>
<rss xmlns:georss="http://www.georss.org/georss"><channel>
  <item>
    <title>Esan (Japan) - Report for 6 August-12 August 2026 - New Unrest</title>
    <description>&lt;p&gt;JMA reported earthquakes.&lt;/p&gt;</description>
    <guid>https://volcano.si.edu/reports_weekly.cfm#vn_285011</guid>
    <pubDate>Thu, 13 Aug 2026 04:03:16 -0400</pubDate>
    <georss:point>41.8050 141.1660</georss:point>
  </item>
  <item>
    <title>Great Sitkin (United States) - Report for 6 August-12 August 2026 - Continuing Eruptive Activity</title>
    <description>&lt;p&gt;Lava effusion continued.&lt;/p&gt;</description>
    <guid>https://volcano.si.edu/reports_weekly.cfm#vn_311120</guid>
    <pubDate>Thu, 13 Aug 2026 04:03:16 -0400</pubDate>
    <georss:point>52.0765 -175.1109</georss:point>
  </item>
  <item>
    <title>Unlocated (Nowhere) - Report - New Unrest</title>
    <pubDate>Thu, 13 Aug 2026 04:03:16 -0400</pubDate>
  </item>
</channel></rss>'''


class VolcanoFeedTests(unittest.TestCase):
    def test_parse_title_splits_name_country_and_status(self):
        self.assertEqual(
            parse_title("Esan (Japan) - Report for 6 August-12 August 2026 - New Unrest"),
            ("Esan", "Japan", "New Unrest"),
        )

    def test_new_activity_is_orange_and_continuing_is_green(self):
        # 주간 보고서 화산은 모두 활동 중이라, 색은 '신규 여부'로만 갈라야 구분이 생긴다
        self.assertEqual(classify_gvp("New Eruptive Activity"), ("Orange", 70))
        self.assertEqual(classify_gvp("Continuing Eruptive Activity"), ("Green", 55))
        self.assertEqual(classify_gvp("New Unrest"), ("Orange", 45))
        self.assertEqual(classify_gvp("Continuing Unrest"), ("Green", 30))

    def test_eruption_outranks_unrest_in_ring_size(self):
        self.assertGreater(classify_gvp("Continuing Eruptive Activity")[1],
                           classify_gvp("Continuing Unrest")[1])

    def test_unknown_status_degrades_to_green(self):
        self.assertEqual(classify_gvp("Something Unexpected"), ("Green", 30))

    def test_korean_status_translates_gvp_wording(self):
        self.assertEqual(korean_status("New Eruptive Activity"), "신규 분출")
        self.assertEqual(korean_status("Continuing Unrest"), "전조활동 지속")

    def test_parse_gvp_emits_iso_dates_without_z_suffix(self):
        # 모니터 HTML의 timeAgo()가 `iso.replace(' ','T') + 'Z'` 로 파싱하므로 Z가 붙으면 안 된다
        incident = parse_gvp(RSS, {})[0]

        self.assertRegex(incident["dateadded"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
        self.assertEqual(incident["dateadded"], "2026-08-13T08:03:16")

    def test_parse_gvp_excludes_volcano_without_coordinates(self):
        names = [i["name"] for i in parse_gvp(RSS, {})]

        self.assertNotIn("Unlocated", names)
        self.assertEqual(len(names), 2)

    def test_usgs_alert_overrides_gvp_wording(self):
        alerts = {"greatsitkin": ("Orange", 70, "감시 (Watch)")}

        incident = next(i for i in parse_gvp(RSS, alerts) if i["name"] == "Great Sitkin")

        self.assertEqual(incident["tags"], "Orange")
        self.assertEqual(incident["severity"], 70)
        self.assertIn("감시 (Watch)", incident["threat"])

    def test_incident_carries_the_shared_monitor_contract(self):
        incident = parse_gvp(RSS, {})[0]

        for key in ("lat", "lon", "name", "country", "dateadded", "threat", "tags", "severity", "reportUrl"):
            self.assertIn(key, incident)
        self.assertIn(incident["tags"], ("Green", "Orange", "Red"))


if __name__ == "__main__":
    unittest.main()
