# Section 5 — High-Level UML Diagrams

**Project:** Ascenda — CSC 648/848, Section 06, Team 1  
**Milestone:** M2 — October 20, 2026  
**Source snapshot:** GitHub `main`, commit `9139ccd99c76c22e8c452f80d4b1d7cc2fb2d5c6` (October 20, 2026 UTC).

**Status convention:** *Implemented in source* indicates relevant backend classes, routes or frontend components exist. *Proposed* means the described behavior is not implemented. All sequences show logical calls; they do not establish deployed service health or populated database records.

## 5.1 High-level UML class diagram — implemented core domain model

The diagram uses selected **actual SQLAlchemy ORM classes** in `app/backend/app/models/`. It is high-level rather than a complete database entity-relationship diagram. `SessionExercise.role` and `SessionExercise.minutes` override or contextualize an `Exercise`'s defaults. `Assessment` is a persisted model; automated evaluation of its results is not represented as implemented. `ExerciseModel` stores metadata rather than playing videos itself.

```mermaid
classDiagram
    direction LR
    class User {
        +int id
        +str email
        +str password_hash
        +str role
    }
    class UserProfile {
        +int user_id
        +list goals
        +str experience_level
        +int days_per_week
        +int session_minutes
    }
    class Assessment {
        +int user_id
        +dict answers
        +int score
        +str experience_level
    }
    class TrainingProgram {
        +int id
        +str name
        +str goal
        +int length_weeks
    }
    class WorkoutSession {
        +int id
        +int program_id
        +str name
        +int position
    }
    class SessionExercise {
        +int workout_session_id
        +int exercise_id
        +str role
        +int sets
        +int reps
        +int minutes
    }
    class Exercise {
        +int id
        +int wger_id
        +str name
        +str description
        +str default_role
        +int default_minutes
    }
    class Equipment {
        +int id
        +str name
    }
    class MuscleGroup {
        +int id
        +str name
    }
    class WorkoutRecord {
        +int id
        +int user_id
        +datetime performed_at
        +int available_minutes
    }
    class PerformanceEntry {
        +int id
        +int exercise_id
        +int reps
        +float weight_kg
        +str status
    }
    class ExerciseModel {
        +int exercise_id
        +str model_url
        +str video_url
    }
    User "1" --> "0..1" UserProfile : profile
    User "1" --> "0..*" Assessment : assessments
    User "1" --> "0..*" WorkoutRecord : owns
    TrainingProgram "1" *-- "0..*" WorkoutSession : sessions
    WorkoutSession "1" *-- "0..*" SessionExercise : items
    SessionExercise "0..*" --> "1" Exercise : exercise
    Exercise "*" --> "*" Equipment : exercise_equipment
    Exercise "*" --> "*" MuscleGroup : exercise_muscles
    UserProfile "*" --> "*" Equipment : user_equipment
    WorkoutRecord "0..*" --> "0..1" WorkoutSession : session
    WorkoutRecord "1" *-- "0..*" PerformanceEntry : entries
    PerformanceEntry "0..*" --> "1" Exercise : exercise
    Exercise "1" --> "0..1" ExerciseModel : model metadata
```

**Scope:** Additional attributes, primary/foreign keys, check constraints, join-table classes (including `ExerciseMuscle` with `is_primary`), serializers, repositories and service modules are present in the source but omitted for readability. Not all represented ORM classes have corresponding user-facing web screens.

## 5.2 High-level UML sequence diagrams

### 5.2.1 Registration and profile setup — R1/R2 (registration implemented in backend; profile editing proposed)

```mermaid
sequenceDiagram
    actor User
    participant UI as Proposed account UI
    participant Auth as FastAPI /api/auth/register
    participant Service as auth service
    participant Repo as users repository
    participant DB as PostgreSQL
    User->>UI: Enter email, password, optional name
    UI->>Auth: POST registration
    Auth->>Service: register()
    Service->>Repo: check email and create user
    Repo->>DB: Query / insert users
    DB-->>Repo: User row
    Repo-->>Service: Registered user
    Service-->>Auth: User and bearer token
    Auth-->>UI: TokenOut
    UI-->>User: Registration confirmation
    Note over User,DB: UserProfile ORM exists no profile-update route was found.
```

The backend also implements `POST /api/auth/login` and `GET /api/auth/me`; it uses password hashing and a bearer-token dependency. The Next.js account-registration/profile workflow is not shown as implemented.

### 5.2.2 Initial fitness assessment — R4 (proposed application flow)

```mermaid
sequenceDiagram
    actor User
    participant UI as Proposed assessment UI
    participant API as Proposed assessment endpoint
    participant Rules as Proposed scoring logic
    participant DB as PostgreSQL Assessment model
    User->>UI: Start assessment and enter answers
    UI->>API: Submit assessment answers
    API->>Rules: Calculate score and starting level
    Rules-->>API: Score and experience level
    API->>DB: Persist Assessment
    DB-->>API: Stored assessment
    API-->>UI: Assessment results
    UI-->>User: Display starting experience level
```

`app/backend/app/models/users.py` defines `Assessment` (`answers`, `score`, `experience_level`) but no implemented assessment endpoint/service or scoring rules were identified in the reviewed source.

### 5.2.3 Filter and view workout sessions — R3/R5/R6 (implemented frontend/backend integration path)

```mermaid
sequenceDiagram
    actor Visitor
    participant UI as Next.js /workouts
    participant Proxy as Next.js API rewrite
    participant Route as FastAPI catalog route
    participant Service as catalog service
    participant Repo as catalog repository
    participant DB as PostgreSQL
    Visitor->>UI: Select muscle, difficulty, maximum minutes
    UI->>Proxy: GET /api/workout-sessions?filters
    Proxy->>Route: Forward request to backend
    Route->>Service: search_workout_sessions()
    Service->>Repo: list_workout_sessions()
    Repo->>DB: Query stored session/exercise relations
    DB-->>Repo: Stored rows
    Repo-->>Service: WorkoutSession objects
    Service-->>Route: Paginated summaries and computed durations
    Route-->>UI: JSON workout-session results
    UI-->>Visitor: Display matching sessions
    opt Visitor requests exercises
        Visitor->>UI: Click show exercises
        UI->>Route: GET /api/workout-sessions/{id} via rewrite
        Route->>Service: get_workout_session()
        Service->>Repo: Read session and model metadata
        Repo-->>Service: Prescriptions and model/video URLs
        Service-->>UI: Workout detail as JSON
        UI-->>Visitor: Show exercises, role, sets and reps
    end
```

The `/workouts` page and FastAPI routes exist in source. The **homepage** exercise catalog still contains hardcoded examples; this diagram does not claim the homepage search controls are connected. Filtering sessions by `max_minutes` is implemented; dynamically modifying a selected workout to fit a time budget is not.

### 5.2.4 Adapt workout to available time — R6 (proposed advanced adaptation)

```mermaid
sequenceDiagram
    actor User
    participant UI as Proposed adjustment UI
    participant API as Proposed adaptation endpoint
    participant Rules as Proposed duration adaptation logic
    participant DB as PostgreSQL
    User->>UI: Enter available minutes
    UI->>API: Request adjusted session
    API->>DB: Fetch SessionExercise prescriptions
    DB-->>API: Roles and exercise minutes
    API->>Rules: Preserve core work and evaluate accessories
    alt Fits after removing permitted accessories
        Rules-->>API: Shortened exercise list
        API-->>UI: Proposed adjusted session
        UI-->>User: Display retained and removed exercises
    else Core exercises exceed available time
        Rules-->>API: Infeasible within time limit
        API-->>UI: Explain constraint
        UI-->>User: Offer another session / time option
    end
```

The actual backend exposes `SessionExercise.role` and computed workout durations, but no implemented `adapt-session` endpoint or dynamic exercise-removal algorithm was identified. Therefore this is an intended enhancement, distinct from current listing filters.

### 5.2.5 Log workout and retrieve history — R8/R9 (backend implemented; frontend integration unverified)

```mermaid
sequenceDiagram
    actor User
    participant Client as Proposed workout logging client
    participant Route as /api/workout-records
    participant Identity as CurrentUser bearer dependency
    participant Service as workouts service
    participant Repo as workouts repository
    participant DB as PostgreSQL
    User->>Client: Enter workout and performance entries
    Client->>Route: POST /api/workout-records with bearer token
    Route->>Identity: Resolve authenticated user
    Identity-->>Route: User
    Route->>Service: create_record()
    Service->>DB: Validate referenced session/exercises
    Service->>Repo: Add WorkoutRecord and PerformanceEntries
    Repo->>DB: Persist records
    DB-->>Service: Saved record
    Service-->>Client: WorkoutRecordOut
    User->>Client: Open history
    Client->>Route: GET /api/workout-records with bearer token
    Route->>Identity: Resolve user
    Route->>Service: list_history()
    Service->>Repo: Retrieve records scoped to user_id
    Repo->>DB: Filter by user ownership
    DB-->>Service: Records and counts
    Service-->>Client: Paginated history
    Client-->>User: Show completed workouts
```

Authentication, write/read routes, validation and user-scoped history retrieval are implemented in the backend source. The inspected Next.js routes do not demonstrate a connected workout logging/history screen.

### 5.2.6 View Scaniverse exercise demonstration — R3 supporting feature (implemented frontend)

```mermaid
sequenceDiagram
    actor Visitor
    participant Page as Next.js HomePage / Exercise Lab
    participant Viewer as ModelViewer / React Three Fiber
    participant Assets as Vercel static public/about assets
    Visitor->>Page: Open Exercise Lab
    Page->>Viewer: Mount GLB viewer
    Viewer->>Assets: Load Scaniverse-exported GLB
    Assets-->>Viewer: Model data
    Viewer-->>Visitor: Show rotatable and zoomable scene
    Visitor->>Page: Play exercise demonstration
    Page->>Assets: Request MP4
    Assets-->>Page: Video bytes
    Page-->>Visitor: Play HTML5 video
```

The GLB model and MP4 demonstrations remain separate media elements in the homepage. The backend additionally defines an `ExerciseModel` table and read endpoints for linked model/video metadata, but the hardcoded homepage GLB viewer does not use that API. No live Niantic REST call, in-scene video plane, 360° recorded playback or volumetric capture is established by this diagram.

## 5.3 Traceability and implementation status

| Sequence | M1 requirement(s) | Status at source snapshot |
|---|---|---|
| Registration and profile | R1, R2 | Registration/auth endpoints implemented in backend; profile UI/updates proposed |
| Initial fitness assessment | R4 | Assessment ORM exists; scoring and submission flow proposed |
| Filter/view workout sessions | R3, R5, R6 | Next.js `/workouts` and database-backed API code exists; deployed dataset not verified |
| Adapt workout to available time | R6 and core/accessory concept | Prescribed roles/durations implemented; adaptive re-planning proposed |
| Log workout and view history | R8, R9 | Backend implemented; user-facing UI integration unverified |
| Spatial exercise demonstration | R3 | Homepage React Three Fiber GLB viewer + independent MP4 playback implemented |

## 5.4 Verification notes for M2 submission

1. Compare attributes against the final Data Definitions V2. The class diagram reflects current backend code, which may not represent every element of the team's planned conceptual data model.
2. Demonstrate `/workouts` returning real persisted workout sessions and detail on the live deployed site; a source-level FastAPI route is not proof of production DB content.
3. Do not describe Niantic capture as a live backend API integration. It is currently an exported GLB embedded in the web product.
4. Treat the registered user's experience assessment and adaptive session modification as proposed unless separately implemented after this commit.
5. If Section 5 is placed in the final DOCX, preserve the headings and Mermaid previews as rendered diagrams/images (rather than raw code blocks) according to instructor formatting.
