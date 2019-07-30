# Copyright 2019 Michael J Simms
"""Computes the hash of an activity. Used to determine uniqueness."""

import hashlib
import sys
import Keys
import SensorAnalyzerFactory

class ActivityHasher(object):
    """Computes the hash of an activity. Used to determine uniqueness."""

    def __init__(self, activity):
        self.activity = activity
        super(ActivityHasher, self).__init__()

    def hash(self):
        """Main analysis routine."""

        # Sanity check.
        if self.activity is None:
            return

        # We're going to hash the activity so we'll know if it's been modified.
        h = hashlib.sha512()

        # Hash the locations.
        print("Hashing locations...")
        if Keys.ACTIVITY_LOCATIONS_KEY in self.activity:
            locations = self.activity[Keys.ACTIVITY_LOCATIONS_KEY]
            for location in locations:
                date_time = location[Keys.LOCATION_TIME_KEY]
                latitude = location[Keys.LOCATION_LAT_KEY]
                longitude = location[Keys.LOCATION_LON_KEY]
                altitude = location[Keys.LOCATION_ALT_KEY]
                h.update(str(date_time).encode('utf-8'))
                h.update(str(latitude).encode('utf-8'))
                h.update(str(longitude).encode('utf-8'))
                h.update(str(altitude).encode('utf-8'))

        # Hash the sensor data.
        print("Hashing sensor data...")
        sensor_types_to_analyze = SensorAnalyzerFactory.supported_sensor_types()
        for sensor_type in sensor_types_to_analyze:
            if sensor_type in self.activity:
                h.update(sensor_type.encode('utf-8'))
                for datum in self.activity[sensor_type]:
                    if sys.version_info[0] < 3:
                        time = str(datum.keys()[0]).encode('utf-8')
                        value = str(datum.values()[0]).encode('utf-8')
                    else:
                        time = str(list(datum.keys())[0]).encode('utf-8')
                        value = str(list(datum.values())[0]).encode('utf-8')
                    h.update(time)
                    h.update(value)

        # Finalize the hash digest.
        hash_str = h.hexdigest()
        return hash_str
