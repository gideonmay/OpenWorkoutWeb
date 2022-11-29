# Copyright 2019 Michael J Simms
"""Generates a swim plan for the specifiied user."""

import Keys
import PlanGenerator
import WorkoutFactory

class SwimPlanGenerator(PlanGenerator.PlanGenerator):
    """Class for generating a swim plan for the specifiied user."""

    def __init__(self, user_id):
        self.user_id = user_id

    def is_workout_plan_possible(self, inputs):
        """Returns TRUE if we can actually generate a plan with the given contraints."""

        # If we're not planning to do any swimming then of course it's possible.
        goal_distance = inputs[Keys.GOAL_SWIM_DISTANCE_KEY]
        if goal_distance < 0.1:
            return True

        has_swimming_pool_access = inputs[Keys.USER_HAS_SWIMMING_POOL_ACCESS]
        has_open_water_swim_access = inputs[Keys.USER_HAS_OPEN_WATER_SWIM_ACCESS]
        return has_swimming_pool_access or has_open_water_swim_access

    def gen_aerobic_swim(self):
        """Utility function for creating an aerobic-focused swim workout."""

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_POOL_SWIM, self.user_id)
        workout.sport_type = Keys.TYPE_POOL_SWIMMING_KEY

        return workout

    def gen_technique_swim(self):
        """Utility function for creating a technique swim workout."""

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_TECHNIQUE_SWIM, self.user_id)
        workout.sport_type = Keys.TYPE_POOL_SWIMMING_KEY

        return workout
        
    def gen_goal_workout(self, goal_distance_meters):
        """Utility function for creating the goal workout/race."""

        # Create the workout object.
        workout = WorkoutFactory.create(Keys.WORKOUT_TYPE_EVENT, self.user_id)
        workout.sport_type = Keys.TYPE_OPEN_WATER_SWIMMING_KEY
        workout.add_distance_interval(1, goal_distance_meters, 0, 0, 0)

        return workout

    def gen_workouts_for_next_week(self, inputs):
        """Generates the workouts for the next week, but doesn't schedule them."""

        workouts = []

        # Extract the necessary inputs.
        goal_distance = inputs[Keys.GOAL_SWIM_DISTANCE_KEY]
        goal = inputs[Keys.PLAN_INPUT_GOAL_KEY]
        goal_type = inputs[Keys.GOAL_TYPE_KEY]
        weeks_until_goal = inputs[Keys.PLAN_INPUT_WEEKS_UNTIL_GOAL_KEY]
        has_swimming_pool_access = inputs[Keys.USER_HAS_SWIMMING_POOL_ACCESS]
        has_open_water_swim_access = inputs[Keys.USER_HAS_OPEN_WATER_SWIM_ACCESS]

        # If the user doesn't have access to a swimming venue then just return.
        if not (has_swimming_pool_access or has_open_water_swim_access):
            return workouts

        # Is this the goal week? If so, add that event.
        if weeks_until_goal == int(0) and PlanGenerator.PlanGenerator.valid_float(goal_distance):
            goal_workout = self.gen_goal_workout(goal_distance)
            workouts.append(goal_workout)

        # If the user has access to a pool then include one technique swim each week.
        if has_swimming_pool_access:
            workouts.append(self.gen_technique_swim())
        elif has_open_water_swim_access:
            workouts.append(self.gen_aerobic_swim())

        # Are we in a taper?
        in_taper = self.is_in_taper(weeks_until_goal, goal)

        # Add the remaining inputs.
        if goal == Keys.GOAL_FITNESS_KEY:
            workouts.append(self.gen_aerobic_swim())
        elif goal == Keys.GOAL_5K_RUN_KEY:
            pass
        elif goal == Keys.GOAL_10K_RUN_KEY:
            pass
        elif goal == Keys.GOAL_15K_RUN_KEY:
            pass
        elif goal == Keys.GOAL_HALF_MARATHON_RUN_KEY:
            pass
        elif goal == Keys.GOAL_MARATHON_RUN_KEY:
            pass
        elif goal == Keys.GOAL_50K_RUN_KEY:
            pass
        elif goal == Keys.GOAL_50_MILE_RUN_KEY:
            pass
        elif goal == Keys.GOAL_SPRINT_TRIATHLON_KEY:
            if not in_taper:
                workouts.append(self.gen_aerobic_swim())
        elif goal == Keys.GOAL_OLYMPIC_TRIATHLON_KEY:
            if not in_taper:
                workouts.append(self.gen_aerobic_swim())
        elif goal == Keys.GOAL_HALF_IRON_DISTANCE_TRIATHLON_KEY:
            if not in_taper:
                workouts.append(self.gen_aerobic_swim())
        elif goal == Keys.GOAL_IRON_DISTANCE_TRIATHLON_KEY:
            if not in_taper:
                workouts.append(self.gen_aerobic_swim())
            workouts.append(self.gen_aerobic_swim())

        return workouts
