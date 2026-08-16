import unittest

from scripts.build_tsunami_feed import field, parse_center, parse_magnitude


def atom(category, magnitude, region, lat="37.753", lon="-122.198"):
    return f'''<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#">
  <entry>
    <title>{region}</title>
    <updated>2026-08-13T15:34:56Z</updated>
    <geo:lat>{lat}</geo:lat>
    <geo:long>{lon}</geo:long>
    <summary type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml">
      <strong>Category:</strong> {category}<br/>
      <strong>Bulletin Issue Time: </strong> 2026.08.13 15:34:56 UTC <br/>
      <strong>Preliminary Magnitude: </strong>{magnitude}(Ml)<br/>
      <strong>Affected Region: </strong>{region}<br/>
      <b>Note:</b> * There is NO tsunami danger from this earthquake.<br/>
    </div></summary>
    <link rel="related" href="https://example.test/cap.xml"/>
    <link rel="alternate" href="https://example.test/bulletin.txt"/>
  </entry>
</feed>'''.encode("utf-8")


class TsunamiFeedTests(unittest.TestCase):
    def test_field_stops_at_the_next_label(self):
        summary = "Category: Information Bulletin Issue Time: 2026.08.13 Preliminary Magnitude: 4.0(Ml)"

        self.assertEqual(field(summary, "Category"), "Information")
        self.assertEqual(field(summary, "Preliminary Magnitude"), "4.0(Ml)")

    def test_parse_magnitude_reads_leading_number(self):
        self.assertEqual(parse_magnitude("4.0(Ml)"), 4.0)
        self.assertEqual(parse_magnitude(""), 0.0)

    def test_warning_maps_to_red_and_information_to_green(self):
        warning = parse_center(atom("Warning", "8.2", "Aleutian Islands"), "NTWC", "센터")[0]
        info = parse_center(atom("Information", "4.0", "California"), "NTWC", "센터")[0]

        self.assertEqual(warning["tags"], "Red")
        self.assertEqual(info["tags"], "Green")

    def test_watch_and_advisory_map_to_orange(self):
        for category in ("Watch", "Advisory"):
            with self.subTest(category=category):
                incident = parse_center(atom(category, "7.1", "Pacific"), "PTWC", "센터")[0]
                self.assertEqual(incident["tags"], "Orange")

    def test_severity_scales_magnitude_but_magnitude_is_kept_for_the_badge(self):
        # 배지는 규모 4.0을 그대로 보여야 하므로 원본 규모를 별도 필드로 남긴다
        incident = parse_center(atom("Information", "4.0", "California"), "NTWC", "센터")[0]

        self.assertEqual(incident["magnitude"], 4.0)
        self.assertEqual(incident["severity"], 40.0)

    def test_bulletin_url_prefers_the_alternate_link(self):
        incident = parse_center(atom("Information", "4.0", "California"), "NTWC", "센터")[0]

        self.assertEqual(incident["reportUrl"], "https://example.test/bulletin.txt")

    def test_entry_without_coordinates_is_skipped(self):
        no_geo = b'''<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry><title>Unlocated</title><updated>2026-08-13T15:34:56Z</updated></entry>
        </feed>'''

        self.assertEqual(parse_center(no_geo, "NTWC", "센터"), [])

    def test_incident_carries_the_shared_monitor_contract(self):
        incident = parse_center(atom("Information", "4.0", "California"), "NTWC", "센터")[0]

        for key in ("lat", "lon", "name", "country", "dateadded", "threat", "tags", "severity", "reportUrl"):
            self.assertIn(key, incident)
        self.assertRegex(incident["dateadded"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


if __name__ == "__main__":
    unittest.main()
