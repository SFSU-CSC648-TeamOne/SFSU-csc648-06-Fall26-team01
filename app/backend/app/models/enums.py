# List of allowed values for certain fields in the database. 
# These are used to validate input and ensure consistency across the application.
 
from enum import Enum

class UserRole(str, Enum):
    user = "user"
    administrator = "administrator"

class ExperienceLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"  
    advanced = "advanced"

class ExerciseRole(str, Enum):
    core = "core"
    accessory = "accessory"

class EntryStatus(str, Enum):
    completed = "completed"
    skipped = "skipped"
    substituted = "substituted"

# added for new engine support
class PrescriptionStatus(str, Enum):
    planned = "planned"
    completed = "completed"
    skipped = "skipped"

class ObservationType(str, Enum):
    training = "training"
    benchmark = "benchmark"

class LoadBasis(str, Enum):
    none = "none"
    bodyweight = "bodyweight"
    added = "added"
    external = "external"
    assisted = "assisted"

class CheckpointType(str, Enum):
    weekly = "weekly"
    program_end = "program_end"

class MovementRelationship(str, Enum):
    primary = "primary"
    secondary = "secondary"
    
def sql_in(enum_cls: type[Enum]) -> str:
    return ", ".join(f"'{e.value}'" for e in enum_cls)