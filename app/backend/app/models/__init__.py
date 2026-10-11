# imports all the models in one place, SQLAlchemy will use the tables 
# and if table is missing, it won't create it

from app.models.catalog import (Equipment, Exercise, ExerciseMuscle, MuscleGroup, 
                                SessionExercise, TrainingProgram, WorkoutSession, exercise_equipment)
from app.models.tracking import PerformanceEntry, WorkoutRecord
from app.models.users import Assessment, User, UserProfile, user_equipment

