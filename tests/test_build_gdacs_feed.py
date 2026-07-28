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


if __name__ == '__main__':
    unittest.main()
