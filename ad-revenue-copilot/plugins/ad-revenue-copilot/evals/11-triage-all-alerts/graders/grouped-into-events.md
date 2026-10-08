---
type: llm
weight: 3
---

Reference: the 20 alerts describe about 6 events:
- 15 June, 3 alerts (channel 21, advertiser 2644, ad unit 5181): one small delivery that stopped; it actually
  stopped on 12-13 June, about 1.5% of daily revenue.
- 17 June: traffic surge on site 346 (+79%), one day.
- 20 June: site 351 up 48%, one day.
- 21 June, 12 alerts (total + 11 slices): ONE event with two causes - advertiser 79 (about 74% of revenue)
  paying a higher eCPM, and a traffic surge on site 345. The geo / device / OS / channel / ad type / ad unit
  alerts are facets of these two.
- 22 June, 2 alerts (device 3, channel 4): the continuation of the 21 June event (revenue still about +30%).
- 24 June: advertiser 16 up about 50%, one day.

PASS if the answer groups the 12 alerts of 21 June into one event (or two closely linked causes: advertiser 79
price and site 345 traffic) instead of treating them as many separate problems, AND treats the 3 alerts of
15 June as one delivery.
FAIL if the answer reports the alerts mostly one by one, or counts more than about 9 separate events.
