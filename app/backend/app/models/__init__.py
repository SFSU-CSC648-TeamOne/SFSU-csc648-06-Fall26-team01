# imports all the models in one place, SQLAlchemy will use the tables 
# and if table is missing, it won't create it

from app.models.catalog import (Equipment, Exercise, ExerciseMuscle, MuscleGroup, 
                                SessionExercise, TrainingProgram, WorkoutSession, exercise_equipment,
                                MovementGroup, ExerciseMovementGroup)
from app.models.tracking import (PerformanceEntry, WorkoutRecord, BodyweightMeasurement,
                                 ProgressCheckpoint)
from app.models.prescription import (WorkoutPrescription, PrescriptionSet,)
from app.models.users import (Assessment, User, UserProfile, user_equipment,)
from app.models.media import ExerciseModel
from app.models.chat import ChatConversation, ChatMessage
from app.models.scans import ExerciseScan
from app.models.program_baseline import ProgramBaseline
from app.models.program_phase import (ProgramPhase, ProgramPhaseType,)
from app.models.adaptation_approval import (AdaptationApproval, AdaptationAdjustmentType,)