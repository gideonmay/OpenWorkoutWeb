# Copyright 2017-2018 Michael J Simms
"""Main application, contains all web page handlers"""

import cherrypy
import datetime
import json
import logging
import mako
import markdown
import os
import sys
import threading
import timeit
import traceback

import Keys
import LocationAnalyzer
import Api
import Units
import UserMgr

from dateutil.tz import tzlocal
from mako.lookup import TemplateLookup
from mako.template import Template


PRODUCT_NAME = 'Straen'

LOGIN_URL = '/login'
DEFAULT_LOGGED_IN_URL = '/all_activities'
HTML_DIR = 'html'


g_stats_lock = threading.Lock()
g_stats_count = {}
g_stats_time = {}


def statistics(function):
    """Function decorator for usage and timing statistics."""

    def wrapper(*args, **kwargs):
        global g_stats_lock
        global g_stats_count
        global g_stats_time

        start = timeit.default_timer()
        result = function(*args, **kwargs)
        end = timeit.default_timer()
        execution_time = end - start

        g_stats_lock.acquire()
        try:
            g_stats_count[function.__name__] = g_stats_count[function.__name__] + 1
            g_stats_time[function.__name__] = g_stats_time[function.__name__] + execution_time
        except:
            g_stats_count[function.__name__] = 1
            g_stats_time[function.__name__] = execution_time
        finally:
            g_stats_lock.release()

        return result

    return wrapper


class RedirectException(Exception):
    """This is thrown when the app needs to redirect to another page."""

    def __init__(self, url):
        self.url = url
        super(RedirectException, self).__init__()


class App(object):
    """Class containing the URL handlers."""

    def __init__(self, user_mgr, data_mgr, root_dir, root_url, google_maps_key):
        self.user_mgr = user_mgr
        self.data_mgr = data_mgr
        self.root_dir = root_dir
        self.root_url = root_url
        self.tempfile_dir = os.path.join(self.root_dir, 'tempfile')
        self.tempmod_dir = os.path.join(self.root_dir, 'tempmod')
        self.google_maps_key = google_maps_key
        self.lifting_activity_html_file = os.path.join(root_dir, HTML_DIR, 'lifting_activity.html')
        self.map_single_html_file = os.path.join(root_dir, HTML_DIR, 'map_single_google.html')
        self.map_multi_html_file = os.path.join(root_dir, HTML_DIR, 'map_multi_google.html')
        self.error_logged_in_html_file = os.path.join(root_dir, HTML_DIR, 'error_logged_in.html')

        self.tempfile_dir = os.path.join(root_dir, 'tempfile')
        if not os.path.exists(self.tempfile_dir):
            os.makedirs(self.tempfile_dir)

        super(App, self).__init__()

    def terminate(self):
        """Destructor"""
        print("Terminating the application...")
        print("Terminating data management...")
        self.data_mgr.terminate()
        self.data_mgr = None
        print("Terminating session management...")
        self.user_mgr.terminate()
        self.user_mgr = None

    def log_error(self, log_str):
        """Writes an error message to the log file."""
        logger = logging.getLogger()
        logger.error(log_str)

    def stats(self):
        """Renders the list of a user's devices."""
        global g_stats_lock
        global g_stats_count
        global g_stats_time

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Get the details of the logged in user.
        user_id, _, user_realname = self.user_mgr.retrieve_user(username)
        if user_id is None:
            self.log_error('Unknown user ID')
            raise RedirectException(LOGIN_URL)

        # Build a list of table rows from the device information.
        page_stats_str = "<td><b>Page</b></td><td><b>Num Accesses</b></td><td><b>Avg Time (secs)</b></td><tr>\n"
        g_stats_lock.acquire()
        try:
            for key, count_value in g_stats_count.iteritems():
                page_stats_str += "\t\t<tr><td>"
                page_stats_str += str(key)
                page_stats_str += "</td><td>"
                page_stats_str += str(count_value)
                page_stats_str += "</td><td>"
                if key in g_stats_time and count_value > 0:
                    total_time = g_stats_time[key]
                    avg_time = total_time / count_value
                    page_stats_str += str(avg_time)
                page_stats_str += "</td></tr>\n"
        finally:
            g_stats_lock.release()

        # The number of users and activities.
        total_users_str = ""
        total_activities_str = ""
        try:
            total_users_str = str(self.data_mgr.total_users_count())
            total_activities_str = str(self.data_mgr.total_activities_count())
        except:
            self.log_error("Exception while getting counts.")

        # Render from template.
        html_file = os.path.join(self.root_dir, HTML_DIR, 'stats.html')
        my_template = Template(filename=html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(True), product=PRODUCT_NAME, root_url=self.root_url, email=username, name=user_realname, page_stats=page_stats_str, total_activities=total_activities_str, total_users=total_users_str)

    def update_track(self, activity_id=None, num=None):
        if activity_id is None:
            return ""
        if num is None:
            return ""

        locations = self.data_mgr.retrieve_most_recent_locations(activity_id, int(num))

        response = "["

        for location in locations:
            if len(response) > 1:
                response += ","
            response += json.dumps({"latitude": location.latitude, "longitude": location.longitude})

        response += "]"

        return response

    def update_metadata(self, activity_id=None):
        if activity_id is None:
            return ""

        response = "["

        names = self.data_mgr.retrieve_metadata(Keys.APP_NAME_KEY, activity_id)
        if names != None and len(names) > 0:
            response += json.dumps({"name": Keys.APP_NAME_KEY, "value": names[-1][1]})

        times = self.data_mgr.retrieve_metadata(Keys.APP_TIME_KEY, activity_id)
        if times != None and len(times) > 0:
            if len(response) > 1:
                response += ","
            localtimezone = tzlocal()
            value_str = datetime.datetime.fromtimestamp(times[-1][1] / 1000, localtimezone).strftime('%Y-%m-%d %H:%M:%S')
            response += json.dumps({"name": Keys.APP_TIME_KEY, "value": value_str})

        distances = self.data_mgr.retrieve_metadata(Keys.APP_DISTANCE_KEY, activity_id)
        if distances != None and len(distances) > 0:
            if len(response) > 1:
                response += ","
            distance = distances[len(distances) - 1]
            value = float(distance.values()[0])
            response += json.dumps({"name": Keys.APP_DISTANCE_KEY, "value": "{:.2f}".format(value)})

        avg_speeds = self.data_mgr.retrieve_metadata(Keys.APP_AVG_SPEED_KEY, activity_id)
        if avg_speeds != None and len(avg_speeds) > 0:
            if len(response) > 1:
                response += ","
            speed = avg_speeds[len(avg_speeds) - 1]
            value = float(speed.values()[0])
            response += json.dumps({"name": Keys.APP_AVG_SPEED_KEY, "value": "{:.2f}".format(value)})

        moving_speeds = self.data_mgr.retrieve_metadata(Keys.APP_MOVING_SPEED_KEY, activity_id)
        if moving_speeds != None and len(moving_speeds) > 0:
            if len(response) > 1:
                response += ","
            speed = moving_speeds[len(moving_speeds) - 1]
            value = float(speed.values()[0])
            response += json.dumps({"name": Keys.APP_MOVING_SPEED_KEY, "value": "{:.2f}".format(value)})

        heart_rates = self.data_mgr.retrieve_sensor_readings(Keys.APP_HEART_RATE_KEY, activity_id)
        if heart_rates != None and len(heart_rates) > 0:
            if len(response) > 1:
                response += ","
            heart_rate = heart_rates[len(heart_rates) - 1]
            value = float(heart_rate.values()[0])
            response += json.dumps({"name": Keys.APP_HEART_RATE_KEY, "value": "{:.2f} bpm".format(value)})

        cadences = self.data_mgr.retrieve_sensor_readings(Keys.APP_CADENCE_KEY, activity_id)
        if cadences != None and len(cadences) > 0:
            if len(response) > 1:
                response += ","
            cadence = cadences[len(cadences) - 1]
            value = float(cadence.values()[0])
            response += json.dumps({"name": Keys.APP_CADENCE_KEY, "value": "{:.2f}".format(value)})

        powers = self.data_mgr.retrieve_sensor_readings(Keys.APP_POWER_KEY, activity_id)
        if powers != None and len(powers) > 0:
            if len(response) > 1:
                response += ","
            power = powers[len(powers) - 1]
            value = float(power.values()[0])
            response += json.dumps({"name": Keys.APP_POWER_KEY, "value": "{:.2f} watts".format(value)})

        response += "]"

        return response

    @staticmethod
    def timestamp_format():
        """The user's desired timestamp format."""
        return "%Y/%m/%d %H:%M:%S"

    @staticmethod
    def timestamp_code_to_str(ts_code):
        """Converts from unix timestamp to human-readable"""
        try:
            return datetime.datetime.fromtimestamp(ts_code).strftime(App.timestamp_format())
        except:
            pass
        return "-"

    def create_navbar(self, logged_in):
        """Helper function for building the navigation bar."""
        navbar_str = "<nav>\n\t<ul>\n"
        if logged_in:
            navbar_str += \
                "\t\t<li><a href=\"" + self.root_url + "/my_activities/\">My Activities</a></li>\n" \
                "\t\t<li><a href=\"" + self.root_url + "/all_activities/\">All Activities</a></li>\n" \
                "\t\t<li><a href=\"" + self.root_url + "/workouts/\">Workouts</a></li>\n" \
                "\t\t<li><a href=\"" + self.root_url + "/gear/\">Gear</a></li>\n" \
                "\t\t<li><a href=\"" + self.root_url + "/following/\">Following</a></li>\n" \
                "\t\t<li><a href=\"" + self.root_url + "/followers/\">Followers</a></li>\n" \
                "\t\t<li><a href=\"" + self.root_url + "/device_list/\">Devices</a></li>\n" \
                "\t\t<li><a href=\"" + self.root_url + "/import_activity/\">Import</a></li>\n" \
                "\t\t<li><a href=\"" + self.root_url + "/profile/\">Profile</a></li>\n" \
                "\t\t<li><a href=\"" + self.root_url + "/settings/\">Settings</a></li>\n" \
                "\t\t<li><a href=\"" + self.root_url + "/logout/\">Log Out</a></li>\n"
        else:
            navbar_str += "\t\t<li><a href=\"" + self.root_url + "/login/\">Log In</a></li>\n"
        navbar_str += "\t</ul>\n</nav>"
        return navbar_str

    def render_comments(self, activity_id, logged_in):
        """Helper function for building the comments string."""
        comments = self.data_mgr.retrieve_activity_comments(activity_id)
        comments_str = ""
        if comments is not None:
            for comment_entry in comments:
                decoded_entry = json.loads(comment_entry)
                commenter_id = decoded_entry[Keys.ACTIVITY_COMMENTER_ID_KEY]
                _, commenter_name = self.user_mgr.retrieve_user_from_id(commenter_id)
                comments_str += "<td><b>"
                comments_str += commenter_name
                comments_str += "</b> says \""
                comments_str += decoded_entry[Keys.ACTIVITY_COMMENT_KEY]
                comments_str += "\"</td><tr>\n"
        if logged_in:
            comments_str += "<td><textarea rows=\"4\" cols=\"100\" maxlength=\"512\" id=\"comment\"></textarea></td><tr>\n"
            comments_str += "<td><button type=\"button\" onclick=\"return create_comment()\">Post</button></td><tr>\n"
        return comments_str

    def render_export_control(self, logged_in, has_location_data, has_accel_data):
        """Helper function for building the comments string."""
        exports_str = ""
        if logged_in:
            exports_str  = "<td>Export Format:</td><tr>\n"
            exports_str += "<td><select id=\"format\" class=\"checkin\" >\n"
            if has_location_data:
                exports_str += "\t<option value=\"tcx\" selected\">TCX</option>\n"
                exports_str += "\t<option value=\"gpx\">GPX</option>\n"
            if has_accel_data:
                exports_str += "\t<option value=\"csv\">CSV</option>\n"
            exports_str += "</select>\n</td><tr>\n"
            exports_str += "<td><button type=\"button\" onclick=\"return export_activity()\">Export</button></td><tr>\n"
        return exports_str

    def render_page_for_lifting_activity(self, email, user_realname, activity_id, activity, logged_in_username, belongs_to_current_user, is_live):
        """Helper function for rendering the map corresonding to a specific device and activity."""

        # Is the user logged in?
        logged_in = logged_in_username is not None

        # Read the accelerometer data (if any).
        accels = []
        if Keys.APP_ACCELEROMETER_KEY in activity:
            accels = activity[Keys.APP_ACCELEROMETER_KEY]

        # Format the accelerometer data.
        x_axis = ""
        y_axis = ""
        z_axis = ""
        for accel in accels:
            time_str = str(accel[Keys.ACCELEROMETER_TIME_KEY])
            x_axis += "\t\t\t\t{ date: new Date(" + time_str + "), value: " + str(accel[Keys.ACCELEROMETER_AXIS_NAME_X]) + " },\n"
            y_axis += "\t\t\t\t{ date: new Date(" + time_str + "), value: " + str(accel[Keys.ACCELEROMETER_AXIS_NAME_Y]) + " },\n"
            z_axis += "\t\t\t\t{ date: new Date(" + time_str + "), value: " + str(accel[Keys.ACCELEROMETER_AXIS_NAME_Z]) + " },\n"

        # Retrieve cached summary data. If summary data has not been computed, then add this activity to the queue and move on without it.
        summary_data = self.data_mgr.retrieve_activity_summary(activity_id)
        if summary_data is None or len(summary_data) == 0:
            self.data_mgr.analyze(activity)

        # Find the sets data.
        sets = None
        if Keys.APP_SETS_KEY in activity:
            sets = activity[Keys.APP_SETS_KEY]
        elif Keys.APP_SETS_KEY in summary_data:
            sets = summary_data[Keys.APP_SETS_KEY]

        # Build the details view.
        details = ""
        if sets is not None:
            details = "<table>\n<td><b>Set</b></td><td><b>Rep Count</b></td><tr>\n"
            set_num = 1
            for current_set in sets:
                details += "<td>"
                details += str(set_num)
                details += "</td><td>"
                details += str(current_set)
                details += "</td><tr>\n"
                set_num = set_num + 1
            details += "</table>\n"

        # Build the summary data view.
        summary = "<ul>\n"
        activity_type = self.data_mgr.retrieve_metadata(Keys.ACTIVITY_TYPE_KEY, activity_id)
        if activity_type is None:
            activity_type = Keys.TYPE_UNSPECIFIED_ACTIVITY
        summary += "\t<li>Activity Type: " + activity_type + "</li>\n"
        name = self.data_mgr.retrieve_metadata(Keys.ACTIVITY_NAME_KEY, activity_id)
        if name is None:
            name = Keys.UNNAMED_ACTIVITY_TITLE
        summary += "\t<li>Name: " + name + "</li>\n"
        tags = self.data_mgr.retrieve_tags(activity_id)
        if tags is not None:
            summary += "\t<li>Tags: "
            for tag in tags:
                summary += tag
                summary += " "
            summary += "</li>\n"
        summary += "</ul>\n"

        # List the comments.
        comments_str = self.render_comments(activity_id, logged_in)

        # List the export options.
        exports_str = self.render_export_control(logged_in, False, Keys.APP_ACCELEROMETER_KEY in activity)

        # Build the page title.
        if is_live:
            page_title = "Live Tracking"
        else:
            page_title = "Activity"

        my_template = Template(filename=self.lifting_activity_html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(logged_in), product=PRODUCT_NAME, root_url=self.root_url, email=email, name=user_realname, pagetitle=page_title, details=details, summary=summary, activityId=activity_id, xAxis=x_axis, yAxis=y_axis, zAxis=z_axis, comments=comments_str, exports=exports_str)

    def render_metadata_for_page(self, key, activity_id):
        """Helper function for processing meatadata and formatting it for display."""
        max_value = 0.0
        data = self.data_mgr.retrieve_metadata(key, activity_id)
        data_str = ""
        if data is not None and isinstance(data, list):
            for datum in data:
                time = datum.keys()[0]
                value = float(datum.values()[0])
                data_str += "\t\t\t\t{ date: new Date(" + str(time) + "), value: " + str(value) + " },\n"
                if value > max_value:
                    max_value = value
        return data_str, max_value

    def render_sensor_data_for_page(self, key, activity_id):
        """Helper function for processing sensor data and formatting it for display."""
        max_value = 0.0
        data = self.data_mgr.retrieve_sensor_readings(key, activity_id)
        data_str = ""
        if data is not None and isinstance(data, list):
            for datum in data:
                time = datum.keys()[0]
                value = float(datum.values()[0])
                data_str += "\t\t\t\t{ date: new Date(" + str(time) + "), value: " + str(value) + " },\n"
                if value > max_value:
                    max_value = value
        return data_str, max_value

    def render_page_for_mapped_activity(self, email, user_realname, activity_id, activity, logged_in_userid, belongs_to_current_user, is_live):
        """Helper function for rendering the map corresonding to a specific activity."""

        # Is the user logged in?
        logged_in = logged_in_userid is not None

        locations = activity[Keys.ACTIVITY_LOCATIONS_KEY]
        if locations is None or len(locations) == 0:
            my_template = Template(filename=self.error_logged_in_html_file, module_directory=self.tempmod_dir)
            return my_template.render(nav=self.create_navbar(logged_in), product=PRODUCT_NAME, root_url=self.root_url, error="There is no data for the specified activity.")

        route = ""
        center_lat = 0
        center_lon = 0
        last_lat = 0
        last_lon = 0

        for location in locations:
            route += "\t\t\t\tnewCoord(" + str(location[Keys.LOCATION_LAT_KEY]) + ", " + str(location[Keys.LOCATION_LON_KEY]) + "),\n"
            last_loc = location

        if len(locations) > 0:
            first_loc = locations[0]
            center_lat = first_loc[Keys.LOCATION_LAT_KEY]
            center_lon = first_loc[Keys.LOCATION_LON_KEY]
            last_lat = last_loc[Keys.LOCATION_LAT_KEY]
            last_lon = last_loc[Keys.LOCATION_LON_KEY]

        # Get all the things.
        current_speeds_str, _ = self.render_metadata_for_page(Keys.APP_CURRENT_SPEED_KEY, activity_id)
        heart_rates_str, max_heart_rate = self.render_sensor_data_for_page(Keys.APP_HEART_RATE_KEY, activity_id)
        cadences_str, max_cadence = self.render_sensor_data_for_page(Keys.APP_CADENCE_KEY, activity_id)
        powers_str, max_power = self.render_sensor_data_for_page(Keys.APP_POWER_KEY, activity_id)
        name = self.data_mgr.retrieve_metadata(Keys.ACTIVITY_NAME_KEY, activity_id)
        activity_type = self.data_mgr.retrieve_metadata(Keys.ACTIVITY_TYPE_KEY, activity_id)
        if activity_type is None:
            activity_type = Keys.TYPE_UNSPECIFIED_ACTIVITY

        # Compute location-based things.
        location_analyzer = LocationAnalyzer.LocationAnalyzer(activity_type)
        location_analyzer.append_locations(locations)

        # Retrieve cached summary data. If summary data has not been computed, then add this activity to the queue and move on without it.
        summary_data = self.data_mgr.retrieve_activity_summary(activity_id)
        if summary_data is None or len(summary_data) == 0:
            self.data_mgr.analyze(activity)

        # Build the summary data view.
        summary = "<ul>\n"

        # Add the activity type.
        summary += "\t<li>Activity Type: " + activity_type + "</li>\n"

        # Add the activity name.
        if name is None:
            name = Keys.UNNAMED_ACTIVITY_TITLE
        summary += "\t<li>Name: " + name + "</li>\n"

        if location_analyzer.total_distance is not None:
            value, value_units = Units.convert_to_preferred_distance_units(self.user_mgr, logged_in_userid, location_analyzer.total_distance, Units.UNITS_DISTANCE_METERS)
            summary += "\t<li>Distance: {:.2f} ".format(value) + Units.get_distance_units_str(value_units) + "</li>\n"
        if location_analyzer.avg_speed is not None:
            value, value_distance_units, value_time_units = Units.convert_to_preferred_speed_units(self.user_mgr, logged_in_userid, location_analyzer.avg_speed, Units.UNITS_DISTANCE_METERS, Units.UNITS_TIME_SECONDS)
            summary += "\t<li>Avg. Speed: {:.2f} ".format(value) + Units.get_speed_units_str(value_distance_units, value_time_units) + "</li>\n"

        # Add summary data that was computed out-of-band and cached.
        if summary_data is not None:

            if Keys.BEST_SPEED in summary_data:
                value, value_distance_units, value_time_units = Units.convert_to_preferred_speed_units(self.user_mgr, logged_in_userid, summary_data[Keys.BEST_SPEED], Units.UNITS_DISTANCE_METERS, Units.UNITS_TIME_SECONDS)
                summary += "\t<li>Max. Speed: {:.2f} ".format(value) + Units.get_speed_units_str(value_distance_units, value_time_units) + "</li>\n"
            if Keys.BEST_1K in summary_data:
                value = Units.convert_speed(1.0 / summary_data[Keys.BEST_1K], Units.UNITS_DISTANCE_MILES, Units.UNITS_TIME_SECONDS, Units.UNITS_DISTANCE_KILOMETERS, Units.UNITS_TIME_HOURS)
                summary += "\t<li>Best KM: {:.2f} ".format(value) + Units.get_speed_units_str(Units.UNITS_DISTANCE_KILOMETERS, Units.UNITS_TIME_HOURS) + "</li>\n"
            if Keys.BEST_MILE in summary_data:
                value = Units.convert_speed(1.0 / summary_data[Keys.BEST_MILE], Units.UNITS_DISTANCE_MILES, Units.UNITS_TIME_SECONDS, Units.UNITS_DISTANCE_MILES, Units.UNITS_TIME_HOURS)
                summary += "\t<li>Best Mile: {:.2f} ".format(value) + Units.get_speed_units_str(Units.UNITS_DISTANCE_MILES, Units.UNITS_TIME_HOURS) + "</li>\n"

        if max_heart_rate > 1:
            summary += "\t<li>Max. Heart Rate: {:.2f} ".format(max_heart_rate) + Units.get_heart_rate_units_str() + "</li>\n"
        if max_cadence:
            summary += "\t<li>Max. Cadence: {:.2f} ".format(max_cadence) + Units.get_cadence_units_str() + "</li>\n"
        if max_power:
            summary += "\t<li>Max. Power: {:.2f} ".format(max_power) + Units.get_power_units_str() + "</li>\n"

        # Add tag data.
        tags = self.data_mgr.retrieve_tags(activity_id)
        if tags is not None:
            summary += "\t<li>Tags: "
            for tag in tags:
                summary += tag
                summary += " "
            summary += "</li>\n"
        summary += "</ul>\n"

        # Build the detailed analysis table.
        details_str = ""
        if summary_data is not None:
            for key in sorted(summary_data):
                details_str += "<td><b>"
                details_str += key
                details_str += "</b></td><td>"
                value = summary_data[key]

                if key.find("Heart Rate") > 0:
                    details_str += "{:.2f}".format(value) + " " + Units.get_heart_rate_units_str()
                elif key.find("Cadence") > 0:
                    details_str += "{:.2f}".format(value) + " " + Units.get_cadence_units_str()
                elif key.find("Power") > 0:
                    details_str += "{:.2f}".format(value) + " " + Units.get_power_units_str()
                elif key.find("Speed") > 0:
                    value, value_distance_units, value_time_units = Units.convert_to_preferred_speed_units(self.user_mgr, logged_in_userid, value, Units.UNITS_DISTANCE_METERS, Units.UNITS_TIME_SECONDS)
                    details_str += "{:.2f}".format(value) + " " + Units.get_speed_units_str(value_distance_units, value_time_units)
                else:
                    details_str += Units.convert_seconds_to_hours_mins_secs(value)
                details_str += "</td><tr>"
        if len(details_str) == 0:
            details_str = "<td><b>No data</b></td><tr>"

        if belongs_to_current_user:
            details_controls_str = "<td><button type=\"button\" onclick=\"return refresh_analysis()\">Refresh Analysis</button></td><tr>\n"
        else:
            details_controls_str = ""

        # List the comments.
        comments_str = self.render_comments(activity_id, logged_in)

        # List the export options.
        exports_str = self.render_export_control(logged_in, True, Keys.APP_ACCELEROMETER_KEY in activity)

        # Build the page title.
        if is_live:
            page_title = "Live Tracking"
        else:
            page_title = "Activity"

        my_template = Template(filename=self.map_single_html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(logged_in), product=PRODUCT_NAME, root_url=self.root_url, email=email, name=user_realname, pagetitle=page_title, summary=summary, googleMapsKey=self.google_maps_key, centerLat=center_lat, lastLat=last_lat, lastLon=last_lon, centerLon=center_lon, route=route, routeLen=len(locations), activityId=activity_id, currentSpeeds=current_speeds_str, heartRates=heart_rates_str, cadences=cadences_str, powers=powers_str, details=details_str, details_controls=details_controls_str, comments=comments_str, exports=exports_str)

    def render_page_for_activity(self, activity, email, user_realname, activity_id, logged_in_userid, belongs_to_current_user, is_live):
        """Helper function for rendering the page corresonding to a specific activity."""

        try:
            if Keys.ACTIVITY_LOCATIONS_KEY in activity and len(activity[Keys.ACTIVITY_LOCATIONS_KEY]) > 0:
                return self.render_page_for_mapped_activity(email, user_realname, activity_id, activity, logged_in_userid, belongs_to_current_user, is_live)
            elif Keys.APP_ACCELEROMETER_KEY in activity or Keys.APP_SETS_KEY in activity:
                return self.render_page_for_lifting_activity(email, user_realname, activity_id, activity, logged_in_userid, belongs_to_current_user, is_live)
            else:
                my_template = Template(filename=self.error_logged_in_html_file, module_directory=self.tempmod_dir)
                return my_template.render(nav=self.create_navbar(logged_in_userid is not None), product=PRODUCT_NAME, root_url=self.root_url, error="There is no data for the specified activity.")
        except:
            traceback.print_exc(file=sys.stdout)
            self.log_error(sys.exc_info()[0])
            self.log_error('Unhandled exception in ' + App.activity.__name__)
        return self.error()

    def render_page_for_multiple_mapped_activities(self, email, user_realname, device_strs, user_id, logged_in):
        """Helper function for rendering the map to track multiple devices."""

        if device_strs is None:
            my_template = Template(filename=self.error_logged_in_html_file, module_directory=self.tempmod_dir)
            return my_template.render(nav=self.create_navbar(logged_in), product=PRODUCT_NAME, root_url=self.root_url, error="No device IDs were specified.")

        route_coordinates = ""
        center_lat = 0
        center_lon = 0
        last_lat = 0
        last_lon = 0
        device_index = 0

        for device_str in device_strs:
            activity_id = self.data_mgr.retrieve_most_recent_activity_id_for_device(device_str)
            if activity_id is None:
                continue

            locations = self.data_mgr.retrieve_locations(activity_id)
            if locations is None:
                continue

            route_coordinates += "\t\t\tvar routeCoordinates" + str(device_index) + " = \n\t\t\t[\n"
            for location in locations:
                route_coordinates += "\t\t\t\tnewCoord(" + str(location[Keys.LOCATION_LAT_KEY]) + ", " + str(location[Keys.LOCATION_LON_KEY]) + "),\n"
                last_loc = location
            route_coordinates += "\t\t\t];\n"
            route_coordinates += "\t\t\taddRoute(routeCoordinates" + str(device_index) + ");\n\n"

            if len(locations) > 0:
                first_loc = locations[0]
                center_lat = first_loc[Keys.LOCATION_LAT_KEY]
                center_lon = first_loc[Keys.LOCATION_LON_KEY]
                last_lat = last_loc[Keys.LOCATION_LAT_KEY]
                last_lon = last_loc[Keys.LOCATION_LON_KEY]

        my_template = Template(filename=self.map_multi_html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(logged_in), product=PRODUCT_NAME, root_url=self.root_url, email=email, name=user_realname, googleMapsKey=self.google_maps_key, centerLat=center_lat, centerLon=center_lon, lastLat=last_lat, lastLon=last_lon, routeCoordinates=route_coordinates, routeLen=len(locations), userId=str(user_id))

    @staticmethod
    def render_user_row(user):
        """Helper function for creating a table row describing a user."""
        row = "<tr>"
        row += "<td>"
        row += user[Keys.USERNAME_KEY]
        row += "</td>"
        row += "<td>"
        row += user[Keys.REALNAME_KEY]
        row += "</td>"
        row += "</tr>\n"
        return row

    def error(self, error_str=None):
        """Renders the error page."""
        try:
            error_html_file = os.path.join(self.root_dir, HTML_DIR, 'error.html')
            my_template = Template(filename=error_html_file, module_directory=self.tempmod_dir)
            if error_str is None:
                error_str = "Internal Error."
            return my_template.render(error=error_str)
        except:
            pass
        return ""

    @statistics
    def live(self, device_str):
        """Renders the map page for the current activity from a single device."""

        # Get the logged in user (if any).
        logged_in_userid = None
        logged_in_username = self.user_mgr.get_logged_in_user()
        if logged_in_username is not None:
            logged_in_userid, _, _ = self.user_mgr.retrieve_user(logged_in_username)

        # Determine the ID of the most recent activity logged from the specified device.
        activity_id = self.data_mgr.retrieve_most_recent_activity_id_for_device(device_str)
        if activity_id is None:
            return self.error()

        # Determine who owns the device.
        device_user = self.user_mgr.retrieve_user_from_device(device_str)
        device_user_id = device_user[Keys.DATABASE_ID_KEY]
        belongs_to_current_user = str(device_user_id) == str(logged_in_userid)

        # Load the activity.
        activity = self.data_mgr.retrieve_activity(activity_id)

        # Determine if the current user can view the activity.
        if not (self.data_mgr.is_activity_public(activity) or belongs_to_current_user):
            return self.error("The requested activity is not public.")

        # Render from template.
        return self.render_page_for_activity(activity, device_user[Keys.USERNAME_KEY], device_user[Keys.REALNAME_KEY], activity_id, logged_in_userid, belongs_to_current_user, True)

    def get_activity_user(self, activity):
        """Returns the user record that corresponds with the given activity."""
        if Keys.ACTIVITY_USER_ID_KEY in activity:
            username, realname = self.user_mgr.retrieve_user_from_id(activity[Keys.ACTIVITY_USER_ID_KEY])
            return activity[Keys.ACTIVITY_USER_ID_KEY], username, realname
        if Keys.ACTIVITY_DEVICE_STR_KEY in activity and len(activity[Keys.ACTIVITY_DEVICE_STR_KEY]) > 0:
            user = self.user_mgr.retrieve_user_from_device(activity[Keys.ACTIVITY_DEVICE_STR_KEY])
            if user is not None:
                return user[Keys.DATABASE_ID_KEY], user[Keys.USERNAME_KEY], user[Keys.REALNAME_KEY]
        return None, None, None

    @statistics
    def activity(self, activity_id):
        """Renders the map page for an activity."""

        # Get the logged in user (if any).
        logged_in_userid = None
        logged_in_username = self.user_mgr.get_logged_in_user()
        if logged_in_username is not None:
            logged_in_userid, _, _ = self.user_mgr.retrieve_user(logged_in_username)

        # Load the activity.
        activity = self.data_mgr.retrieve_activity(activity_id)
        if activity is None:
            return self.error("The requested activity does not exist.")

        # Determine who owns the device, and hence the activity.
        device_user_id, username, realname = self.get_activity_user(activity)
        belongs_to_current_user = str(device_user_id) == str(logged_in_userid)
        if username is None:
            username = ""
        if realname is None:
            realname = ""

        # Determine if the current user can view the activity.
        if not (self.data_mgr.is_activity_public(activity) or belongs_to_current_user):
            return self.error("The requested activity is not public.")

        # Render from template.
        return self.render_page_for_activity(activity, username, realname, activity_id, logged_in_userid, belongs_to_current_user, False)

    @statistics
    def device(self, device_str):
        """Renders the map page for a single device."""

        # Get the logged in user (if any).
        logged_in_userid = None
        logged_in_username = self.user_mgr.get_logged_in_user()
        if logged_in_username is not None:
            logged_in_userid, _, _ = self.user_mgr.retrieve_user(logged_in_username)

        # Get the activity ID being requested. If one is not provided then get the latest activity for the device
        activity_id = cherrypy.request.params.get("activity_id")
        if activity_id is None:
            activity_id = self.data_mgr.retrieve_most_recent_activity_id_for_device(device_str)
            if activity_id is None:
                return self.error()

        # Determine who owns the device.
        device_user = self.user_mgr.retrieve_user_from_device(device_str)
        device_user_id = device_user[Keys.DATABASE_ID_KEY]
        belongs_to_current_user = str(device_user_id) == str(logged_in_userid)

        # Load the activity.
        activity = self.data_mgr.retrieve_activity(activity_id)
        if activity is None:
            return self.error("The requested activity does not exist.")

        # Determine if the current user can view the activity.
        if not (self.data_mgr.is_activity_public(activity) or belongs_to_current_user):
            return self.error("The requested activity is not public.")

        # Render from template.
        return self.render_page_for_activity(activity, device_user[Keys.USERNAME_KEY], device_user[Keys.REALNAME_KEY], activity_id, logged_in_userid, belongs_to_current_user, False)

    @statistics
    def my_activities(self):
        """Renders the list of the specified user's activities."""

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Get the details of the logged in user.
        user_id, _, user_realname = self.user_mgr.retrieve_user(username)
        if user_id is None:
            self.log_error('Unknown user ID')
            raise RedirectException(LOGIN_URL)

        # Render from template.
        html_file = os.path.join(self.root_dir, HTML_DIR, 'my_activities.html')
        my_template = Template(filename=html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(True), product=PRODUCT_NAME, root_url=self.root_url, email=username, name=user_realname)

    @statistics
    def all_activities(self):
        """Renders the list of all activities the specified user is allowed to view."""

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Get the details of the logged in user.
        user_id, _, user_realname = self.user_mgr.retrieve_user(username)
        if user_id is None:
            self.log_error('Unknown user ID')
            raise RedirectException(LOGIN_URL)

        # Render from template.
        html_file = os.path.join(self.root_dir, HTML_DIR, 'all_activities.html')
        my_template = Template(filename=html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(True), product=PRODUCT_NAME, root_url=self.root_url, email=username, name=user_realname)

    @statistics
    def workouts(self):
        """Renders the list of all workouts the specified user is allowed to view."""

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Get the details of the logged in user.
        user_id, _, user_realname = self.user_mgr.retrieve_user(username)
        if user_id is None:
            self.log_error('Unknown user ID')
            raise RedirectException(LOGIN_URL)

        # Render from template.
        html_file = os.path.join(self.root_dir, HTML_DIR, 'workouts.html')
        my_template = Template(filename=html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(True), product=PRODUCT_NAME, root_url=self.root_url, email=username, name=user_realname)

    @statistics
    def gear(self):
        """Renders the list of all gear belonging to the logged in user."""

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Get the details of the logged in user.
        user_id, _, user_realname = self.user_mgr.retrieve_user(username)
        if user_id is None:
            self.log_error('Unknown user ID')
            raise RedirectException(LOGIN_URL)

        bikes = "<table>"
        shoes = "<table>"
        gear_list = self.data_mgr.retrieve_gear_for_user(user_id)
        for gear in gear_list:
            if Keys.GEAR_TYPE_KEY in gear:
                row_str = ""
                if Keys.GEAR_NAME_KEY in gear:
                    row_str += "<td>"
                    row_str += gear[Keys.GEAR_NAME_KEY]
                    row_str += "</td>"
                row_str += "<tr>"
                gear_type = gear[Keys.GEAR_TYPE_KEY]
                if gear_type == GEAR_TYPE_BIKE:
                    bikes += row_str
                elif gear_type == GEAR_TYPE_SHOES:
                    shoes += row_str
        bikes += "</table>"
        shoes == "</table>"

        # Render from template.
        html_file = os.path.join(self.root_dir, HTML_DIR, 'gear.html')
        my_template = Template(filename=html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(True), product=PRODUCT_NAME, root_url=self.root_url, email=username, name=user_realname, bikes=bikes, shoes=shoes)

    @statistics
    def following(self):
        """Renders the list of users the specified user is following."""

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Get the details of the logged in user.
        user_id, _, user_realname = self.user_mgr.retrieve_user(username)
        if user_id is None:
            self.log_error('Unknown user ID')
            raise RedirectException(LOGIN_URL)

        # Get the list of users followed by the logged in user.
        users_following = self.user_mgr.list_users_followed(user_id)
        users_list_str = "Not currently following anyone."
        if users_following is not None and isinstance(users_following, list):
            if len(users_following) > 0:
                users_list_str = ""
                for user in users_following:
                    users_list_str += self.render_user_row(user)

        # Render from template.
        html_file = os.path.join(self.root_dir, HTML_DIR, 'following.html')
        my_template = Template(filename=html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(True), product=PRODUCT_NAME, root_url=self.root_url, email=username, name=user_realname, users_list=users_list_str)

    @statistics
    def followers(self):
        """Renders the list of users that are following the specified user."""

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Get the details of the logged in user.
        user_id, _, user_realname = self.user_mgr.retrieve_user(username)
        if user_id is None:
            self.log_error('Unknown user ID')
            raise RedirectException(LOGIN_URL)

        # Get the list of users following the logged in user.
        users_followed_by = self.user_mgr.list_followers(user_id)
        users_list_str = "Not currently being followed by anyone."
        if users_followed_by is not None and isinstance(users_followed_by, list):
            if len(users_followed_by) > 0:
                users_list_str = ""
                for user in users_followed_by:
                    users_list_str += self.render_user_row(user)

        # Render from template.
        html_file = os.path.join(self.root_dir, HTML_DIR, 'followers.html')
        my_template = Template(filename=html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(True), product=PRODUCT_NAME, root_url=self.root_url, email=username, name=user_realname, users_list=users_list_str)

    @statistics
    def device_list(self):
        """Renders the list of a user's devices."""

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Get the details of the logged in user.
        user_id, _, user_realname = self.user_mgr.retrieve_user(username)
        if user_id is None:
            self.log_error('Unknown user ID')
            raise RedirectException(LOGIN_URL)

        # Get the list of devices that are associated with the user.
        devices = self.user_mgr.retrieve_user_devices(user_id)

        # Build a list of table rows from the device information.
        device_list_str = ""
        if devices is not None and isinstance(devices, list):
            device_list_str += "<td><b>Unique Identifier</b></td><td><b>Last Heard From</b></td><tr>\n"
            for device in devices:
                activity = self.data_mgr.retrieve_most_recent_activity_for_device(device)
                device_list_str += "\t\t<tr>"
                device_list_str += "<td><a href=\"" + self.root_url + "/device/" + device + "\">"
                device_list_str += device
                device_list_str += "</a></td><td>"
                if activity is not None:
                    device_list_str += "<script>document.write(unix_time_to_local_string(" + str(activity[Keys.ACTIVITY_TIME_KEY]) + "))</script>"
                device_list_str += "</td></tr>\n"

        # Render from template.
        html_file = os.path.join(self.root_dir, HTML_DIR, 'device_list.html')
        my_template = Template(filename=html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(True), product=PRODUCT_NAME, root_url=self.root_url, email=username, name=user_realname, device_list=device_list_str)

    @statistics
    def upload(self, ufile):
        """Processes an request from the upload form."""

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Get the details of the logged in user.
        user_id, _, _ = self.user_mgr.retrieve_user(username)
        if user_id is None:
            self.log_error('Unknown user ID')
            raise RedirectException(LOGIN_URL)

        # Parse the file and store it's contents in the database.
        file_data = ufile.file.read()
        self.data_mgr.import_file(username, user_id, file_data, ufile.filename)

        raise RedirectException(DEFAULT_LOGGED_IN_URL)

    @statistics
    def manual_entry(self, activity_type):
        """Called when the user selects an activity type, indicatig they want to make a manual data entry."""
        print activity_type

    @statistics
    def import_activity(self):
        """Renders the import page."""

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Get the details of the logged in user.
        user_id, _, user_realname = self.user_mgr.retrieve_user(username)
        if user_id is None:
            self.log_error('Unknown user ID')
            raise RedirectException(LOGIN_URL)

        # Build the list options for manual entry.
        activity_type_list = self.data_mgr.retrieve_activity_types()
        activity_type_list_str = "\t\t\t<option value=\"-\">-</option>\n"
        for activity_type in activity_type_list:
            activity_type_list_str += "\t\t\t<option value=\"" + activity_type + "\">" + activity_type + "</option>\n"

        # Render from template.
        html_file = os.path.join(self.root_dir, HTML_DIR, 'import.html')
        my_template = Template(filename=html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(True), product=PRODUCT_NAME, root_url=self.root_url, email=username, name=user_realname, activity_type_list=activity_type_list_str)

    @statistics
    def profile(self):
        """Renders the user's profile page."""

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Get the details of the logged in user.
        user_id, _, user_realname = self.user_mgr.retrieve_user(username)
        if user_id is None:
            self.log_error('Unknown user ID')
            raise RedirectException(LOGIN_URL)

        # Get the current settings.
        selected_height = self.user_mgr.retrieve_user_setting(user_id, Keys.HEIGHT_KEY)
        selected_weight = self.user_mgr.retrieve_user_setting(user_id, Keys.WEIGHT_KEY)
        selected_gender = self.user_mgr.retrieve_user_setting(user_id, Keys.GENDER_KEY)

        # Render the user's height.
        if selected_height is None:
            selected_height = ""

        # Render the user's weight.
        if selected_weight is None:
            selected_weight = ""

        # Render the privacy option.
        gender_options = "\t\t<option value=\"Male\""
        if selected_gender == Keys.GENDER_MALE_KEY:
            gender_options += " selected"
        gender_options += ">Male</option>\n"
        gender_options += "\t\t<option value=\"Female\""
        if selected_gender == Keys.GENDER_FEMALE_KEY:
            gender_options += " selected"
        gender_options += ">Female</option>"

        # Render from the template.
        html_file = os.path.join(self.root_dir, HTML_DIR, 'profile.html')
        my_template = Template(filename=html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(True), product=PRODUCT_NAME, root_url=self.root_url, name=user_realname, weight=selected_weight, height=selected_height, gender_options=gender_options)

    @statistics
    def settings(self):
        """Renders the user's settings page."""

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Get the details of the logged in user.
        user_id, _, user_realname = self.user_mgr.retrieve_user(username)
        if user_id is None:
            self.log_error('Unknown user ID')
            raise RedirectException(LOGIN_URL)

        # Get the current settings.
        selected_default_privacy = self.user_mgr.retrieve_user_setting(user_id, Keys.DEFAULT_PRIVACY)
        selected_units = self.user_mgr.retrieve_user_setting(user_id, Keys.PREFERRED_UNITS_KEY)

        # Render the privacy option.
        privacy_options = "\t\t<option value=\"Public\""
        if selected_default_privacy == Keys.ACTIVITY_VISIBILITY_PUBLIC:
            privacy_options += " selected"
        privacy_options += ">Public</option>\n"
        privacy_options += "\t\t<option value=\"Private\""
        if selected_default_privacy == Keys.ACTIVITY_VISIBILITY_PRIVATE:
            privacy_options += " selected"
        privacy_options += ">Private</option>"

        # Render the units
        unit_options = "\t\t<option value=\"Metric\""
        if selected_units == Keys.UNITS_METRIC_KEY:
            unit_options += " selected"
        unit_options += ">Metric</option>\n"
        unit_options += "\t\t<option value=\"Standard\""
        if selected_units == Keys.UNITS_STANDARD_KEY:
            unit_options += " selected"
        unit_options += ">Standard</option>"

        # Render from the template.
        html_file = os.path.join(self.root_dir, HTML_DIR, 'settings.html')
        my_template = Template(filename=html_file, module_directory=self.tempmod_dir)
        return my_template.render(nav=self.create_navbar(True), product=PRODUCT_NAME, root_url=self.root_url, email=username, name=user_realname, privacy_options=privacy_options, unit_options=unit_options)

    @statistics
    def api(self, user_id, method, params):
        """Handles an API request."""
        api = Api.Api(self.user_mgr, self.data_mgr, self.tempfile_dir, user_id, self.root_url)
        handled, response = api.handle_api_1_0_request(method, params)
        return handled, response

    def submit_login(self, email, password):
        """Processes a login."""
        if email is None or password is None:
            raise Exception("An email address and password were not provided.")
        elif self.user_mgr.authenticate_user(email, password):
            self.user_mgr.create_new_session(email)
            raise RedirectException(DEFAULT_LOGGED_IN_URL)
        raise Exception("Unknown error.")

    def submit_new_login(self, email, realname, password1, password2):
        """Creates a new login."""
        if self.user_mgr.create_user(email, realname, password1, password2, ""):
            self.user_mgr.create_new_session(email)
            raise RedirectException(DEFAULT_LOGGED_IN_URL)
        raise Exception("Unknown error.")

    @statistics
    def login(self):
        """Renders the login page."""

        # If a user is already logged in then go straight to the landing page.
        username = self.user_mgr.get_logged_in_user()
        if username is not None:
            raise RedirectException(DEFAULT_LOGGED_IN_URL)

        html = ""
        readme_file_name = os.path.join(self.root_dir, 'README.md')
        with open(readme_file_name, 'r') as readme_file:
            md = readme_file.read()
            extensions = ['extra', 'smarty']
            html = markdown.markdown(md, extensions=extensions, output_format='html5')

        login_html_file = os.path.join(self.root_dir, HTML_DIR, 'login.html')
        my_template = Template(filename=login_html_file, module_directory=self.tempmod_dir)
        return my_template.render(product=PRODUCT_NAME, root_url=self.root_url, readme=html)

    @statistics
    def create_login(self):
        """Renders the create login page."""
        create_login_html_file = os.path.join(self.root_dir, HTML_DIR, 'create_login.html')
        my_template = Template(filename=create_login_html_file, module_directory=self.tempmod_dir)
        return my_template.render(product=PRODUCT_NAME, root_url=self.root_url)

    @statistics
    def logout(self):
        """Ends the logged in session."""

        # Get the logged in user.
        username = self.user_mgr.get_logged_in_user()
        if username is None:
            raise RedirectException(LOGIN_URL)

        # Clear the session.
        self.user_mgr.clear_session()

        # Send the user back to the login screen.
        raise RedirectException(LOGIN_URL)

    @statistics
    def about(self):
        """Renders the about page."""
        about_html_file = os.path.join(self.root_dir, HTML_DIR, 'about.html')
        my_template = Template(filename=about_html_file, module_directory=self.tempmod_dir)
        return my_template.render(product=PRODUCT_NAME, root_url=self.root_url)

    @statistics
    def status(self):
        """Renders the status page. Used as a simple way to tell if the site is up."""
        return "Up"
