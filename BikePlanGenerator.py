# Copyright 2019 Michael J Simms
"""Generates a bike plan for the specifiied user."""

import Keys
import WorkoutFactory

class BikePlanGenerator(object):
    """Class for generating a bike plan for the specifiied user."""

    def __init__(self, user_id, training_philosophy):
        self.user_id = user_id

        # The training philosophy indicates how much time we intended
        # to spend in each training zone.
        if training_philosophy == Keys.TRAINING_PHILOSOPHY_THRESHOLD:
            self.training_philosophy = Keys.TID_THRESHOLD
        elif training_philosophy == Keys.TRAINING_PHILOSOPHY_POLARIZED:
            self.training_philosophy = Keys.TID_POLARIZED
        elif training_philosophy == Keys.TRAINING_PHILOSOPHY_PYRAMIDAL:
            self.training_philosophy = Keys.TID_PYRAMIDAL
        else:
            self.training_philosophy = Keys.TID_POLARIZED

    def is_workout_plan_possible(self, inputs):
        """Returns TRUE if we can actually generate a plan with the given contraints."""
        return True

    def gen_interval_ride(self):
        """Utility function for creating an interval workout."""

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_SPEED_INTERVAL_RIDE, self.user_id)
        workout.sport_type = Keys.TYPE_CYCLING_KEY

        return workout

    def gen_tempo_ride(self):
        """Utility function for creating a tempo ride."""

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_TEMPO_RIDE, self.user_id)
        workout.sport_type = Keys.TYPE_CYCLING_KEY

        return workout

    def gen_easy_ride(self):
        """Utility function for creating an easy ride."""

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_EASY_RIDE, self.user_id)
        workout.sport_type = Keys.TYPE_CYCLING_KEY

        return workout

    def gen_sweet_spot_ride(self):
        """Utility function for creating a sweet spot ride."""

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_SWEET_SPOT_RIDE, self.user_id)
        workout.sport_type = Keys.TYPE_CYCLING_KEY

        return workout

    def gen_workouts_for_next_week(self, inputs):
        """Generates the workouts for the next week, but doesn't schedule them."""

        workouts = []

        # Extract the necessary inputs.
        goal_distance = inputs[Keys.GOAL_RUN_DISTANCE_KEY]
        goal = inputs[Keys.PLAN_INPUT_GOAL_KEY]
        goal_type = inputs[Keys.GOAL_TYPE_KEY]
        weeks_until_goal = inputs[Keys.PLAN_INPUT_WEEKS_UNTIL_GOAL_KEY]
        avg_bike_distance = inputs[Keys.PLAN_INPUT_AVG_CYCLING_DISTANCE_IN_FOUR_WEEKS]

        # Add critical workouts:
        # Long ride, culminating in (maybe) an overdistance ride.


        return workouts
