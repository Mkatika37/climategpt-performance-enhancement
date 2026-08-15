Source: NASA LANCE - VNP14IMG_NRT active fire detection - World
Scale/Resolution: 375-meter
Update Frequency: Hourly (depending on source availability) using the aggregated live feed methodology
Area Covered: World

The VIIRS thermal activity layer can be used to visualize and assess wildfires worldwide. However, it should be noted that this dataset contains many “false positives” (e.g., oil/natural gas wells or volcanoes) since the satellite will detect any large thermal signal.

Fire points in this service are generally available within 3 1/4 hours after detection by a VIIRS device. LANCE estimates availability at around 3 hours after detection, and esri livefeeds check for updates every 20 minutes from LANCE.

Even though these data display as point features, each point in fact represents a pixel that is >= 375 m high and wide. A point feature means somewhere in this pixel at least one "hot" spot was detected which may be a fire.

VIIRS is a scanning radiometer device aboard the Suomi NPP, NOAA-20, and NOAA-21 satellites that collects imagery and radiometric measurements of the land, atmosphere, cryosphere, and oceans in several visible and infrared bands. The VIIRS Thermal Hotspots and Fire Activity layer is a livefeed from a subset of the overall VIIRS imagery, in particular from NASA's VNP14IMG_NRT active fire detection product. The source downloads are monitored automatically and retrieved from LANCE, NASA's near real time data and imagery site, every 20 minutes when updates detected.

The 375-m data complements the 1-km Moderate Resolution Imaging Spectroradiometer (MODIS) Thermal Hotspots and Fire Activity layer; they both show good agreement in hotspot detection but the improved spatial resolution of the 375 m data provides a greater response over fires of relatively small areas and provides improved mapping of large fire perimeters.

# Attribute information

**Latitude and Longitude**: The center point location of the 375 m (approximately) pixel flagged as containing one or more fires/hotspots.
**Satellite**: Whether the detection was picked up by the Suomi NPP satellite (N) or NOAA-20 satellite (1) or NOAA-21 satellite (2). For best results, use the virtual field WhichSatellite, redefined by an arcade expression, that gives the complete satellite name.
**Confidence**: The detection confidence is a quality flag of the individual hotspot/active fire pixel. This value is based on a collection of intermediate algorithm quantities used in the detection process. It is intended to help users gauge the quality of individual hotspot/fire pixels. Confidence values are set to low, nominal and high. Low confidence daytime fire pixels are typically associated with areas of sun glint and lower relative temperature anomaly (<15K) in the mid-infrared channel I4. Nominal confidence pixels are those free of potential sun glint contamination during the day and marked by strong (>15K) temperature anomaly in either day or nighttime data. High confidence fire pixels are associated with day or nighttime saturated pixels.
Please note: Low confidence nighttime pixels occur only over the geographic area extending from 11 deg E to 110 deg W and 7 deg N to 55 deg S. This area describes the region of influence of the South Atlantic Magnetic Anomaly which can cause spurious brightness temperatures in the mid-infrared channel I4 leading to potential false positive alarms. These have been removed from the NRT data distributed by FIRMS.
**FRP**: Fire Radiative Power. Depicts the pixel-integrated fire radiative power in MW (MegaWatts). FRP provides information on the measured radiant heat output of detected fires. The amount of radiant heat energy liberated per unit time (the Fire Radiative Power) is thought to be related to the rate at which fuel is being consumed (Wooster et. al. (2005)).
**DayNight**: D = Daytime fire, N = Nighttime fire
**Hours Old**: Derived field that provides age of record in hours between Acquisition date/time and latest update date/time. 0 = less than 1 hour ago, 1 = less than 2 hours ago, 2 = less than 3 hours ago, and so on.

# Note about near real time data:
Near real time data is not checked thoroughly before it's posted on LANCE or downloaded and posted to the Living Atlas. NASA's goal is to get vital fire information to its customers within three hours of observation time. However, the data is screened by a confidence algorithm which seeks to help users gauge the quality of individual hotspot/fire points. Low confidence daytime fire pixels are typically associated with areas of sun glint and lower relative temperature anomaly (<15K) in the mid-infrared channel I4. Nominal confidence pixels are those free of potential sun glint contamination during the day and marked by strong (>15K) temperature anomaly in either day or nighttime data. High confidence fire pixels are associated with day or nighttime saturated pixels.
