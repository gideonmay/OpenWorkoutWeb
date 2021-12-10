# Copyright 2019 Michael J Simms
"""Generates a run plan for the specifiied user."""

import math
import numpy as np
import random
from scipy.stats import norm

import Keys
import Units
import WorkoutFactory

# Max zone 1, zone 2, zone 3 total intensity distributions for each training philosophy
TID_THRESHOLD = [55, 55, 20]
TID_POLARIZED = [85, 10, 25]
TID_PYRAMIDAL = [75, 25, 10]

class RunPlanGenerator(object):
    """Class for generating a run plan for the specifiied user."""

    def __init__(self, user_id, training_intensity_distribution):
        self.user_id = user_id

        self.cutoff_pace_1 = 0.0
        self.cutoff_pace_2 = 0.0

        if training_intensity_distribution == Keys.TRAINING_INTENSITY_DIST_THRESHOLD:
            self.training_intensity_distribution = TID_THRESHOLD
        elif training_intensity_distribution == Keys.TRAINING_INTENSITY_DIST_POLARIZED:
            self.training_intensity_distribution = TID_POLARIZED
        elif training_intensity_distribution == Keys.TRAINING_INTENSITY_DIST_PYRAMIDAL:
            self.training_intensity_distribution = TID_PYRAMIDAL

        self.clear_intensity_distribution()

    def is_workout_plan_possible(self, inputs):
        """Returns TRUE if we can actually generate a plan with the given contraints."""
        return True

    @staticmethod
    def valid_float(value):
        return type(value) == float and value > 0.1

    @staticmethod
    def find_nearest(array, value):
        array = np.asarray(array)
        idx = (np.abs(array - value)).argmin()
        return array[idx]

    @staticmethod
    def nearest_interval_distance(distance, min_distance_in_meters):
        """Given a distance, returns the nearest 'common' interval distance,"""
        """i.e., if given 407 meters, returns 400 meters, because no one runs 407 meter intervals."""
        if distance < min_distance_in_meters:
            distance = min_distance_in_meters
        metric_intervals = [ 400, 800, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 12000, 15000, 20000, 21000, 25000 ]
        us_customary_intervals = [ 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 3.1, 5.0, 6.0, 6.2, 8.0, 10.0, 12.0, 13.1 ]
        return RunPlanGenerator.find_nearest(metric_intervals, distance)

    @staticmethod
    def round_distance(distance):
        return float(math.ceil(distance / 100.0)) * 100.0

    def clear_intensity_distribution(self):
        """Resets all intensity distribution tracking variables."""

        # Distribution of distance spent in each intensity zone.
        # 0 index is least intense.
        self.intensity_distribution_meters = []
        self.intensity_distribution_meters.append(0.0)
        self.intensity_distribution_meters.append(0.0)
        self.intensity_distribution_meters.append(0.0)

        # Distribution of time spent in each intensity zone.
        # 0 index is least intense.
        self.intensity_distribution_seconds = []
        self.intensity_distribution_seconds.append(0)
        self.intensity_distribution_seconds.append(0)
        self.intensity_distribution_seconds.append(0)

    def update_intensity_distribution(self, seconds, meters):
        """Updates the variables used to track intensity distribution."""

         # Distance not specified.
        if meters < 0.01:
            pace = 0.0
        else:
            pace = seconds / meters

        # Above L2 pace.
        if pace > self.cutoff_pace_2:
            self.intensity_distribution_seconds[2] += seconds
            self.intensity_distribution_meters[2] += meters

        # Above L1 pace.
        elif pace > self.cutoff_pace_1:
            self.intensity_distribution_seconds[1] += seconds
            self.intensity_distribution_meters[1] += meters

        # Easy pace.
        else:
            self.intensity_distribution_seconds[0] += seconds
            self.intensity_distribution_meters[0] += meters

    def check_intensity_distribution(self):
        """How far are these workouts from the ideal intensity distribution?"""
        total_meters = sum(self.intensity_distribution_meters)
        intensity_distribution_percent = [(x / total_meters) * 100.0 for x in self.intensity_distribution_meters]
        intensity_distribution_score = sum([abs(x - y) for x, y in zip(intensity_distribution_percent, self.training_intensity_distribution)])
        return intensity_distribution_score

    def gen_easy_run(self, pace, min_run_distance, max_run_distance):
        """Utility function for creating an easy run of some random distance between min and max."""

        # An easy run needs to be at least a couple of kilometers.
        if min_run_distance < 2000:
            min_run_distance = 2000
        if max_run_distance < 2000:
            max_run_distance = 2000

        # Roll the dice to figure out the distance.
        run_distance = random.uniform(min_run_distance, max_run_distance)
        interval_distance_meters = round(run_distance, -3)

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_EASY_RUN, self.user_id)
        workout.sport_type = Keys.TYPE_RUNNING_KEY
        workout.add_interval(1, interval_distance_meters, pace, 0, 0)

        # Tally up the easy and hard distance so we can keep the weekly plan in check.
        self.update_intensity_distribution(interval_distance_meters * pace, interval_distance_meters)

        return workout

    def gen_tempo_run(self, tempo_run_pace, easy_run_pace, max_run_distance):
        """Utility function for creating a tempo workout."""

        # Decide on the number of intervals and their distance.
        num_intervals = 1
        temp_distance = (30.0 * tempo_run_pace) / num_intervals
        interval_distance_meters = RunPlanGenerator.nearest_interval_distance(temp_distance, 2000.0)

        # Sanity check.
        if interval_distance_meters > max_run_distance:
            interval_distance_meters = max_run_distance
        if interval_distance_meters < 1000:
            interval_distance_meters = 1000

        warmup_duration = 10 * 60 # Ten minute warmup
        cooldown_duration = 10 * 60 # Ten minute cooldown

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_TEMPO_RUN, self.user_id)
        workout.sport_type = Keys.TYPE_RUNNING_KEY
        workout.add_warmup(warmup_duration)
        workout.add_interval(num_intervals, interval_distance_meters, tempo_run_pace, 0, 0)
        workout.add_cooldown(cooldown_duration)

        # Tally up the easy and hard distance so we can keep the weekly plan in check.
        total_rest_meters = ((num_intervals - 1) * interval_distance_meters)
        total_hard_meters = (num_intervals * interval_distance_meters)
        self.update_intensity_distribution(total_rest_meters * easy_run_pace, total_rest_meters)
        self.update_intensity_distribution(total_hard_meters * tempo_run_pace, total_hard_meters)
        self.update_intensity_distribution(warmup_duration, easy_run_pace)
        self.update_intensity_distribution(cooldown_duration, easy_run_pace)

        return workout

    def gen_threshold_run(self, threshold_run_pace, easy_run_pace, max_run_distance):
        """Utility function for creating a threshold workout."""

        # Decide on the number of intervals and their distance.
        temp_distance = 20.0 * threshold_run_pace
        interval_distance_meters = RunPlanGenerator.nearest_interval_distance(temp_distance, 2000.0)

        # Sanity check.
        if interval_distance_meters > max_run_distance:
            interval_distance_meters = max_run_distance
        if interval_distance_meters < 1000:
            interval_distance_meters = 1000

        warmup_duration = 10 * 60 # Ten minute warmup
        cooldown_duration = 10 * 60 # Ten minute cooldown

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_THRESHOLD_RUN, self.user_id)
        workout.sport_type = Keys.TYPE_RUNNING_KEY
        workout.add_warmup(warmup_duration)
        workout.add_interval(1, interval_distance_meters, threshold_run_pace, 0, 0)
        workout.add_cooldown(cooldown_duration)

        # Tally up the easy and hard distance so we can keep the weekly plan in check.
        self.update_intensity_distribution(interval_distance_meters * threshold_run_pace, interval_distance_meters)
        self.update_intensity_distribution(warmup_duration, easy_run_pace)
        self.update_intensity_distribution(cooldown_duration, easy_run_pace)

        return workout

    def gen_speed_run(self, short_interval_run_pace, speed_run_pace, easy_run_pace, goal_distance):
        """Utility function for creating a speed/interval workout."""

        # Constants.
        MIN_REPS_INDEX = 0
        MAX_REPS_INDEX = 1
        REP_DISTANCE_INDEX = 2

        warmup_duration = 10 * 60 # Ten minute warmup
        cooldown_duration = 10 * 60 # Ten minute cooldown

        # Build a collection of possible run interval sessions, sorted by target distance. Order is { min reps, max reps, distance in meters }.
        possible_workouts = [ [ 4, 8, 100 ], [ 4, 8, 200 ], [ 4, 8, 400 ], [ 4, 8, 600 ], [ 2, 8, 800 ], [ 2, 6, 1000 ], [ 2, 4, 1600 ] ]

        # Build a probability density function for selecting the workout. Longer goals should tend towards longer intervals and so on.
        num_possible_workouts = len(possible_workouts)
        x = np.arange(0, num_possible_workouts, 1)
        center_index = int(num_possible_workouts / 2)
        densities = norm.pdf(x, loc=center_index)

        # Make sure the densities array adds up to one.
        total_densities = sum(densities)
        if total_densities < 1.0:
            densities[center_index] += (1.0 - total_densities)

        # If the goal is less than a 10K then favor the shorter interval workouts. If greater than a 1/2 marathon, favor the longer.
        if goal_distance < 10000:
            mod_densities = np.append(densities[1:len(densities)], densities[0])
        elif goal_distance >= Units.METERS_PER_MARATHON:
            mod_densities = np.append(densities[-1], densities[0:len(densities)-1])
            mod_densities = np.append(densities[-1], densities[0:len(densities)-1])
        elif goal_distance >= Units.METERS_PER_HALF_MARATHON:
            mod_densities = np.append(densities[-1], densities[0:len(densities)-1])
        else:
            mod_densities = densities

        # Select the workout.
        selected_interval_workout_index = np.random.choice(x, p=mod_densities)
        selected_interval_workout = possible_workouts[selected_interval_workout_index]

        # Determine the pace for this workout.
        if selected_interval_workout[REP_DISTANCE_INDEX] < 1000:
            interval_pace = short_interval_run_pace
        else:
            interval_pace = speed_run_pace

        # Determine the number of reps for this workout.
        selected_reps = np.random.choice(range(selected_interval_workout[MIN_REPS_INDEX], selected_interval_workout[MAX_REPS_INDEX], 2))

        # Fetch the distance for this workout.
        interval_distance = selected_interval_workout[REP_DISTANCE_INDEX]

        # Determine the rest interval distance. This will be some multiplier of the interval.
        rest_interval_distance = interval_distance * np.random.choice([1, 1.5, 2])

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_SPEED_RUN, self.user_id)
        workout.sport_type = Keys.TYPE_RUNNING_KEY
        workout.add_warmup(warmup_duration)
        workout.add_interval(selected_reps, interval_distance, interval_pace, rest_interval_distance, easy_run_pace)
        workout.add_cooldown(cooldown_duration)

        # Tally up the easy and hard distance so we can keep the weekly plan in check.
        total_rest_meters = ((selected_reps - 1) * rest_interval_distance)
        total_hard_meters = (selected_reps * interval_distance)
        self.update_intensity_distribution(total_rest_meters * easy_run_pace, total_rest_meters)
        self.update_intensity_distribution(total_hard_meters * interval_pace, total_hard_meters)
        self.update_intensity_distribution(warmup_duration, 0.0)
        self.update_intensity_distribution(cooldown_duration, 0.0)

        return workout

    def gen_long_run(self, long_run_pace, longest_run_in_four_weeks, min_run_distance, max_run_distance):
        """Utility function for creating a long run workout."""

        # Long run should be 10% longer than the previous long run, within the bounds provided by min and max.
        long_run_distance = longest_run_in_four_weeks * 1.1
        if long_run_distance > max_run_distance:
            long_run_distance = max_run_distance
        if long_run_distance < min_run_distance:
            long_run_distance = min_run_distance
        interval_distance_meters = RunPlanGenerator.round_distance(long_run_distance)

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_LONG_RUN, self.user_id)
        workout.sport_type = Keys.TYPE_RUNNING_KEY
        workout.add_interval(1, interval_distance_meters, long_run_pace, 0, 0)

        # Tally up the easy and hard distance so we can keep the weekly plan in check.
        self.update_intensity_distribution(interval_distance_meters * long_run_pace, interval_distance_meters)

        return workout

    def gen_free_run(self, easy_run_pace):
        """Utility function for creating a free run workout."""

        # Roll the dice to figure out the distance.
        run_distance = random.uniform(3000, 10000)
        interval_distance_meters = round(run_distance, -3)

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_FREE_RUN, self.user_id)
        workout.sport_type = Keys.TYPE_RUNNING_KEY
        workout.add_interval(1, interval_distance_meters, 0, 0, 0)

        # Tally up the easy and hard distance so we can keep the weekly plan in check.
        self.update_intensity_distribution(interval_distance_meters * easy_run_pace, interval_distance_meters)

        return workout

    def gen_hill_repeats(self):
        """Utility function for creating a hill session."""

        # Roll the dice to figure out the distance.
        run_distance = random.uniform(3000, 7000)
        interval_distance_meters = round(run_distance, -3)

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_HILL_REPEATS, self.user_id)
        workout.sport_type = Keys.TYPE_RUNNING_KEY
        workout.add_interval(1, interval_distance_meters, 0, 0, 0)

        return workout

    def gen_fartlek_run(self):
        """Utility function for creating a fartlek session."""

        # Roll the dice to figure out the distance.
        run_distance = random.uniform(3000, 10000)
        interval_distance_meters = round(run_distance, -3)

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_FARTLEK_RUN, self.user_id)
        workout.sport_type = Keys.TYPE_RUNNING_KEY
        workout.add_interval(1, interval_distance_meters, 0, 0, 0)

        return workout

    def gen_workouts_for_next_week(self, inputs):
        """Generates the workouts for the next week, but doesn't schedule them."""

        workouts = []

        # 3 Critical runs: Speed session, tempo or threshold run, and long run

        goal_distance = inputs[Keys.GOAL_RUN_DISTANCE_KEY]
        goal = inputs[Keys.PLAN_INPUT_GOAL_KEY]
        goal_type = inputs[Keys.GOAL_TYPE_KEY]
        weeks_until_goal = inputs[Keys.PLAN_INPUT_WEEKS_UNTIL_GOAL_KEY]
        short_interval_run_pace = inputs[Keys.SHORT_INTERVAL_RUN_PACE]
        functional_threshold_pace = inputs[Keys.FUNCTIONAL_THRESHOLD_PACE]
        speed_run_pace = inputs[Keys.SPEED_RUN_PACE]
        tempo_run_pace = inputs[Keys.TEMPO_RUN_PACE]
        long_run_pace = inputs[Keys.LONG_RUN_PACE]
        easy_run_pace = inputs[Keys.EASY_RUN_PACE]
        longest_run_in_four_weeks = inputs[Keys.PLAN_INPUT_LONGEST_RUN_IN_FOUR_WEEKS_KEY]
        longest_run_week_1 = inputs[Keys.PLAN_INPUT_LONGEST_RUN_WEEK_1_KEY]
        longest_run_week_2 = inputs[Keys.PLAN_INPUT_LONGEST_RUN_WEEK_2_KEY]
        longest_run_week_3 = inputs[Keys.PLAN_INPUT_LONGEST_RUN_WEEK_3_KEY]
        avg_run_distance = inputs[Keys.PLAN_INPUT_AVG_RUNNING_DISTANCE_IN_FOUR_WEEKS]
        num_runs = inputs[Keys.PLAN_INPUT_NUM_RUNS_LAST_FOUR_WEEKS]
        exp_level = inputs[Keys.PLAN_INPUT_EXPERIENCE_LEVEL_KEY]
        #comfort_level = inputs[Keys.PLAN_INPUT_STRUCTURED_TRAINING_COMFORT_LEVEL_KEY]

        # Handle situation in which the user hasn't run in four weeks.
        if not RunPlanGenerator.valid_float(longest_run_in_four_weeks):
            workouts.append(self.gen_free_run(easy_run_pace))
            workouts.append(self.gen_free_run(easy_run_pace))
            return workouts
        
        # Handle situation in which the user hasn't run *much* in the last four weeks.
        if num_runs is None or num_runs < 4:
            workouts.append(self.gen_free_run(easy_run_pace))
            workouts.append(self.gen_free_run(easy_run_pace))
            return workouts

        # No pace data?
        if not (RunPlanGenerator.valid_float(short_interval_run_pace) and RunPlanGenerator.valid_float(speed_run_pace) and RunPlanGenerator.valid_float(tempo_run_pace) and RunPlanGenerator.valid_float(long_run_pace) and RunPlanGenerator.valid_float(easy_run_pace)):
            raise Exception("No run pace data.")

        # If the long run has been increasing for the last three weeks then give the person a break.
        if longest_run_week_1 and longest_run_week_2 and longest_run_week_3:
            if longest_run_week_1 >= longest_run_week_2 and longest_run_week_2 >= longest_run_week_3:
                longest_run_in_four_weeks *= 0.75

        # Cutoff paces.
        self.cutoff_pace_1 = tempo_run_pace
        self.cutoff_pace_2 = speed_run_pace

        # Are we in a taper?
        # Taper: 2 weeks for a marathon or more, 1 week for a half marathon or less
        in_taper = False
        if weeks_until_goal <= 2 and goal == Keys.GOAL_MARATHON_RUN_KEY:
            in_taper = True
        if weeks_until_goal <= 1 and goal == Keys.GOAL_HALF_MARATHON_RUN_KEY:
            in_taper = True

        # Compute the longest run needed to accomplish the goal.
        # If the goal distance is a marathon then the longest run should be somewhere between 18 and 22 miles.
        # The non-taper equation was derived by playing with trendlines in a spreadsheet.
        if in_taper:
            max_long_run_distance = 0.4 * goal_distance
        else:
            max_long_run_distance = ((-0.002 * goal_distance) *  (-0.002 * goal_distance)) + (0.7 * goal_distance) + 4.4

        # Handle situation in which the user is already meeting or exceeding the goal distance.
        if longest_run_in_four_weeks >= max_long_run_distance:
            longest_run_in_four_weeks = max_long_run_distance

        # Distance ceilings for easy and tempo runs.
        if exp_level <= 5:
            max_easy_run_distance = longest_run_in_four_weeks * 0.60
            max_tempo_run_distance = longest_run_in_four_weeks * 0.40
        else:
            max_easy_run_distance = longest_run_in_four_weeks * 0.75
            max_tempo_run_distance = longest_run_in_four_weeks * 0.50

        # Don't make any runs (other than intervals, tempo runs, etc.) shorter than this.
        min_run_distance = avg_run_distance * 0.5
        if min_run_distance > max_easy_run_distance:
            min_run_distance = max_easy_run_distance

        iter_count = 0
        best_intensity_distribution_score = None
        best_workouts = []
        done = False
        while not done:

            workouts = []

            # Keep track of the number of easy miles/kms and the number of hard miles/kms we're expecting the user to run so we can balance the two.
            self.clear_intensity_distribution()

            # Add a long run.
            long_run_workout = self.gen_long_run(long_run_pace, longest_run_in_four_weeks, min_run_distance, max_long_run_distance)
            workouts.append(long_run_workout)

            # Add an easy run.
            easy_run_workout = self.gen_easy_run(easy_run_pace, min_run_distance, max_easy_run_distance)
            workouts.append(easy_run_workout)

            # Add a tempo run. Run should be 20-30 minutes in duration.
            tempo_run_workout = self.gen_tempo_run(tempo_run_pace, easy_run_pace, max_tempo_run_distance)
            workouts.append(tempo_run_workout)

            # The user cares about speed as well as completing the distance. Also note that we should add strides to one of the other workouts.
            if goal_type.lower() == Keys.GOAL_TYPE_SPEED.lower():

                # Decide which workout we're going to do.
                workout_probability = random.uniform(0, 100)

                if workout_probability < 50:

                    # Add an interval/speed session.
                    interval_workout = self.gen_speed_run(short_interval_run_pace, speed_run_pace, easy_run_pace, goal_distance)
                    workouts.append(interval_workout)

                else:

                    # Add a threshold session.
                    interval_workout = self.gen_threshold_run(functional_threshold_pace, easy_run_pace, goal_distance)
                    workouts.append(interval_workout)

            # Add an easy run.
            easy_run_workout = self.gen_easy_run(easy_run_pace, min_run_distance, max_easy_run_distance)
            workouts.append(easy_run_workout)

            # How far are these workouts from the ideal intensity distribution?
            intensity_distribution_score = self.check_intensity_distribution()
            if best_intensity_distribution_score is None or intensity_distribution_score < best_intensity_distribution_score:
                best_intensity_distribution_score = intensity_distribution_score
                best_workouts = workouts

            # This is used to make sure we don't loop forever.
            iter_count = iter_count + 1

            # Exit conditions:
            if iter_count >= 6:
                done = True

        # Calculate the total stress for each workout.
        for workout in best_workouts:
            workout.calculate_estimated_intensity_score(functional_threshold_pace)

        return best_workouts
