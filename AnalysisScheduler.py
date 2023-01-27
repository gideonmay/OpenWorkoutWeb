# -*- coding: utf-8 -*-
# 
# # MIT License
# 
# Copyright (c) 2019 Mike Simms
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""Schedules computationally expensive analysis tasks"""

import logging
import sys
import traceback
import uuid

class AnalysisScheduler(object):
    """Class for scheduling computationally expensive analysis tasks."""

    def __init__(self):
        super(AnalysisScheduler, self).__init__()

    def log_error(self, log_str):
        """Writes an error message to the log file."""
        logger = logging.getLogger()
        logger.error(log_str)

    def add_activity_to_analysis_queue(self, activity):
        """Adds the activity ID to the list of activities to be analyzed."""
        """Returns [celery task id, our task id]."""
        from bson.json_util import dumps
        from ActivityAnalyzer import analyze_activity

        try:
            activity_str = dumps(activity)
            internal_task_id = uuid.uuid4()
            analysis_task = analyze_activity.delay(activity_str, internal_task_id)
            return analysis_task.task_id, internal_task_id
        except:
            self.log_error(traceback.format_exc())
            self.log_error(sys.exc_info()[0])
        return None, None

    def add_personal_record_analysis_to_queue(self, user_id):
        """Adds the user ID to the list of users to have their personal records updated."""
        from ActivityAnalyzer import analyze_personal_records

        try:
            internal_task_id = uuid.uuid4()
            analysis_task = analyze_personal_records.delay(user_id, internal_task_id)
            return analysis_task.task_id, internal_task_id
        except:
            self.log_error(traceback.format_exc())
            self.log_error(sys.exc_info()[0])
        return None, None
