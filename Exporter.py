# Copyright 2018 Michael J Simms
"""Writes GPX and TCX files."""

import DataMgr
import Keys
import GpxFileWriter
import TcxFileWriter

class Exporter(object):
    """Exporter for GPX and TCX location files."""

    def __init__(self):
        super(Exporter, self).__init__()

    def export_as_csv(self, file_name, activity):
        """Creates a CSV file for accelerometer data."""
        with open(file_name, 'wt') as local_file:
            if Keys.APP_ACCELEROMETER_KEY in activity:
                accel_readings = activity[Keys.APP_ACCELEROMETER_KEY]
                for reading in accel_readings:
                    accel_time = reading[Keys.ACCELEROMETER_TIME_KEY]
                    accel_x = reading[Keys.ACCELEROMETER_AXIS_NAME_X]
                    accel_y = reading[Keys.ACCELEROMETER_AXIS_NAME_Y]
                    accel_z = reading[Keys.ACCELEROMETER_AXIS_NAME_Z]
                    local_file.write(str(accel_time) + "," + str(accel_x) + "," + str(accel_y) + "," + str(accel_z) + "\n")
        return True

    def nearest_sensor_reading(self, time_ms, current_reading, sensor_iter):
        try:
            if current_reading is None:
                current_reading = sensor_iter.next()
            else:
                sensor_time = int(current_reading.keys()[0])
                while sensor_time < time_ms:
                    current_reading = sensor_iter.next()
                    sensor_time = int(current_reading.keys()[0])
        except StopIteration:
            return None
        return current_reading

    def export_as_gpx(self, file_name, activity):
        """Creates a GPX file."""
        locations = []
        cadence_readings = []
        temp_readings = []
        power_readings = []

        if Keys.APP_LOCATIONS_KEY in activity:
            locations = activity[Keys.APP_LOCATIONS_KEY]
        if Keys.APP_CADENCE_KEY in activity:
            cadence_readings = activity[Keys.APP_CADENCE_KEY]
        if Keys.APP_HEART_RATE_KEY in activity:
            hr_readings = activity[Keys.APP_HEART_RATE_KEY]
        if Keys.APP_TEMP_KEY in activity:
            temp_readings = activity[Keys.APP_TEMP_KEY]
        if Keys.APP_POWER_KEY in activity:
            power_readings = activity[Keys.APP_POWER_KEY]

        location_iter = iter(locations)
        if len(locations) == 0:
            raise Exception("No locations for this activity.")

        cadence_iter = iter(cadence_readings)
        nearest_hr = iter(hr_readings)
        temp_iter = iter(temp_readings)
        power_iter = iter(power_readings)

        nearest_cadence = None
        nearest_hr = None
        nearest_temp = None
        nearest_power = None

        writer = GpxFileWriter.GpxFileWriter()
        writer.create_gpx_file(file_name)

        done = False
        while not done:
            try:
                current_location = location_iter.next()
                current_time = current_location[Keys.LOCATION_TIME_KEY]

                nearest_cadence = self.nearest_sensor_reading(current_time, nearest_cadence, cadence_iter)
                nearest_hr = self.nearest_sensor_reading(current_time, nearest_hr, hr_iter)
                nearest_temp = self.nearest_sensor_reading(current_time, nearest_temp, temp_iter)
                nearest_power = self.nearest_sensor_reading(current_time, nearest_power, power_iter)
            except StopIteration:
                done = True

    def export_as_tcx(self, file_name, activity):
        """Creates a TCX file."""
        locations = []
        cadence_readings = []
        hr_readings = []
        temp_readings = []
        power_readings = []

        if Keys.APP_LOCATIONS_KEY in activity:
            locations = activity[Keys.APP_LOCATIONS_KEY]
        if Keys.APP_CADENCE_KEY in activity:
            cadence_readings = activity[Keys.APP_CADENCE_KEY]
        if Keys.APP_HEART_RATE_KEY in activity:
            hr_readings = activity[Keys.APP_HEART_RATE_KEY]
        if Keys.APP_TEMP_KEY in activity:
            temp_readings = activity[Keys.APP_TEMP_KEY]
        if Keys.APP_POWER_KEY in activity:
            power_readings = activity[Keys.APP_POWER_KEY]

        location_iter = iter(locations)
        if len(locations) == 0:
            raise Exception("No locations for this activity.")

        cadence_iter = iter(cadence_readings)
        temp_iter = iter(temp_readings)
        power_iter = iter(power_readings)
        hr_iter = iter(hr_readings)

        nearest_cadence = None
        nearest_temp = None
        nearest_power = None
        nearest_hr = None

        writer = TcxFileWriter.TcxFileWriter()
        writer.create_tcx_file(file_name)
        writer.start_activity(activity[Keys.ACTIVITY_TYPE_KEY])

        lap_start_time_ms = locations[0][Keys.LOCATION_TIME_KEY]
        lap_end_time_ms = 0

        writer.write_id(lap_start_time_ms / 1000)

        done = False
        while not done:

            writer.start_lap(lap_start_time_ms)
            writer.start_track()

            while not done:

                try:
                    current_location = location_iter.next()
                    current_time = current_location[Keys.LOCATION_TIME_KEY]

                    nearest_cadence = self.nearest_sensor_reading(current_time, nearest_cadence, cadence_iter)
                    nearest_hr = self.nearest_sensor_reading(current_time, nearest_hr, hr_iter)
                    nearest_temp = self.nearest_sensor_reading(current_time, nearest_temp, temp_iter)
                    nearest_power = self.nearest_sensor_reading(current_time, nearest_power, power_iter)

                    writer.start_trackpoint()
                    writer.store_time(current_time)
                    writer.store_position(current_location[Keys.LOCATION_LAT_KEY], current_location[Keys.LOCATION_LON_KEY])
                    writer.store_altitude_meters(current_location[Keys.LOCATION_ALT_KEY])

                    if nearest_cadence is not None:
                        writer.store_cadence_rpm(nearest_cadence.values()[0])
                    if nearest_hr is not None:
                        writer.store_heart_rate_bpm(nearest_hr.values()[0])

                    if nearest_temp is not None or nearest_power is not None:
                        writer.start_trackpoint_extensions()
                        if nearest_temp is not None:
                            pass
                        if nearest_power is not None:
                            writer.store_power_in_watts(nearest_power.values()[0])
                        writer.end_trackpoint_extensions()

                    writer.end_trackpoint()
                except StopIteration:
                    done = True

            writer.end_track()

        writer.end_activity()
        writer.close_file()

    def export(self, data_mgr, activity_id, file_name, file_type):
        activity = data_mgr.retrieve_activity(activity_id)
        if file_type == 'csv':
            self.export_as_csv(file_name, activity)
        elif file_type == 'gpx':
            self.export_as_gpx(file_name, activity)
        elif file_type == 'tcx':
            self.export_as_tcx(file_name, activity)
        else:
            raise Exception("Invalid file type specified.")
