import unittest

from scripts.build_gdacs_feed import parse_feed


RSS = b'''<?xml version="1.0"?>
<rss xmlns:gdacs="http://www.gdacs.org" xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#"><channel>
  <item><title>Wildfire Alpha</title><link>https://example.test/wf</link><gdacs:eventtype>WF</gdacs:eventtype><gdacs:eventname>Alpha Fire</gdacs:eventname><gdacs:country>Exampleland</gdacs:country><gdacs:fromdate>2026-07-28T00:00:00Z</gdacs:fromdate><gdacs:alertlevel>Orange</gdacs:alertlevel><gdacs:severity value="42">42 ha</gdacs:severity><geo:lat>12.5</geo:lat><geo:long>34.5</geo:long></item>
  <item><title>Cyclone Bravo</title><link>https://example.test/tc</link><gdacs:eventtype>TC</gdacs:eventtype><gdacs:eventname>Bravo</gdacs:eventname><gdacs:country>Ocean</gdacs:country><gdacs:fromdate>2026-07-28T01:00:00Z</gdacs:fromdate><gdacs:alertlevel>Red</gdacs:alertlevel><gdacs:severity value="80">80 km/h</gdacs:severity><geo:lat>-10</geo:lat><geo:long>140</geo:long></item>
</channel></rss>'''


class GdacsFeedTests(unittest.TestCase):
    def test_parse_feed_separates_wildfires_and_tropical_cyclones(self):
        feed = parse_feed(RSS)

        self.assertEqual(feed['wildfire'][0]['name'], 'Alpha Fire')
        self.assertEqual(feed['wildfire'][0]['lat'], 12.5)
        self.assertEqual(feed['typhoon'][0]['name'], 'Bravo')
        self.assertEqual(feed['typhoon'][0]['tags'], 'Red')

    def test_parse_feed_reads_live_gdacs_georss_point_coordinates(self):
        live_shape = b'''<?xml version="1.0"?>
        <rss xmlns:gdacs="http://www.gdacs.org" xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#" xmlns:georss="http://www.georss.org/georss"><channel>
          <item><title>Cyclone Noul</title><link>https://example.test/tc</link><gdacs:eventtype>TC</gdacs:eventtype><gdacs:eventname>NOUL-26</gdacs:eventname><gdacs:fromdate>2026-07-28T01:00:00Z</gdacs:fromdate><geo:Point></geo:Point><georss:point>22.9 114.5</georss:point></item>
        </channel></rss>'''

        incident = parse_feed(live_shape)['typhoon'][0]

        self.assertEqual(incident['lat'], 22.9)
        self.assertEqual(incident['lon'], 114.5)

    def test_parse_feed_excludes_event_without_coordinates(self):
        missing_location = b'''<?xml version="1.0"?>
        <rss xmlns:gdacs="http://www.gdacs.org"><channel>
          <item><title>Unlocated Cyclone</title><gdacs:eventtype>TC</gdacs:eventtype><gdacs:eventname>UNLOCATED</gdacs:eventname></item>
        </channel></rss>'''

        self.assertEqual(parse_feed(missing_location)['typhoon'], [])


FLOOD_RSS = b'''<?xml version="1.0"?>
<rss xmlns:gdacs="http://www.gdacs.org" xmlns:georss="http://www.georss.org/georss"><channel>
  <item><title>Flood in Japan</title><link>https://example.test/fl</link><gdacs:eventtype>FL</gdacs:eventtype><gdacs:country>Japan</gdacs:country><gdacs:fromdate>Thu, 13 Aug 2026 01:00:00 GMT</gdacs:fromdate><gdacs:alertlevel>Green</gdacs:alertlevel><gdacs:severity unit="" value="0">Magnitude 0 </gdacs:severity><gdacs:population unit="Population Affected" value="8">8 deaths and 7359 displaced </gdacs:population><georss:point>35.58 140.13</georss:point></item>
  <item><title>Flood in China</title><link>https://example.test/fl2</link><gdacs:eventtype>FL</gdacs:eventtype><gdacs:country>China</gdacs:country><gdacs:fromdate>Fri, 31 Jul 2026 01:00:00 GMT</gdacs:fromdate><gdacs:alertlevel>Green</gdacs:alertlevel><gdacs:severity unit="" value="0">Magnitude 0 </gdacs:severity><gdacs:population unit="Population Affected" value="0">0 deaths and 65593 displaced </gdacs:population><georss:point>30.0 114.0</georss:point></item>
</channel></rss>'''


class FloodFeedTests(unittest.TestCase):
    def test_parse_feed_collects_floods(self):
        floods = parse_feed(FLOOD_RSS)['flood']

        self.assertEqual(len(floods), 2)
        self.assertEqual(floods[0]['country'], 'Japan')
        self.assertEqual(floods[0]['lat'], 35.58)

    def test_flood_impact_text_is_korean(self):
        japan = parse_feed(FLOOD_RSS)['flood'][0]

        self.assertEqual(japan['threat'], '사망 8명 · 이재민 7,359명')
        self.assertEqual(japan['deaths'], 8)
        self.assertEqual(japan['displaced'], 7359)

    def test_flood_ring_metric_counts_displaced_not_only_deaths(self):
        # GDACS 는 홍수 severity 를 항상 0으로 보내므로, 사망자만 쓰면 링이 전부 최소 크기가 된다
        floods = {i['country']: i for i in parse_feed(FLOOD_RSS)['flood']}

        self.assertEqual(floods['Japan']['severity'], round(8 + 7359 / 200, 1))
        self.assertGreater(floods['China']['severity'], floods['Japan']['severity'])
        self.assertEqual(floods['China']['deaths'], 0)

    def test_dates_are_iso_without_z_so_the_monitor_can_parse_them(self):
        # RFC822 를 그대로 두면 timeAgo() 의 replace(' ','T') 가 첫 공백만 바꿔 "NaN일 전"이 된다
        feed = parse_feed(FLOOD_RSS)

        for incident in feed['flood']:
            with self.subTest(country=incident['country']):
                self.assertRegex(incident['dateadded'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$')

    def test_wildfire_and_typhoon_dates_are_iso_too(self):
        feed = parse_feed(RSS)

        for kind in ('wildfire', 'typhoon'):
            with self.subTest(kind=kind):
                self.assertRegex(feed[kind][0]['dateadded'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$')


if __name__ == '__main__':
    unittest.main()
