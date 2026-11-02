// Program data for the BW and LDW programs.
// Each program = a pool of 10 exercises, combined into 5 workout days per week, for 4 weeks.
// Days 6 and 7 of every week are rest days (28 calendar days, 20 workout days).

export type Role = "core" | "accessory";

export type Exercise = {
  id: string;
  name: string;
  muscle: string;
  equipment: string;
  baseMinutes: number; // minutes in week 1 (sets + rest)
  /** Name of the exercise in the database whose video/scans to show. Leave out when it is the same as `name`. */
  demo?: string;
};

export type DayTemplate = {
  title: string;
  focus: string;
  items: { exerciseId: string; role: Role }[];
};

export type Program = {
  slug: "bw" | "ldw";
  name: string;
  fullName: string;
  tagline: string;
  description: string;
  equipment: string[];
  exercises: Exercise[];
  days: DayTemplate[]; // exactly 5 templates
  weekSchemes: { sets: number; reps: number; minutesFactor: number }[]; // exactly 4
};

export const WEEKS = 4;
export const WORKOUT_DAYS_PER_WEEK = 5;
export const DAYS_PER_WEEK = 7;

const BW: Program = {
  slug: "bw",
  name: "BW",
  fullName: "Body-Weight Program",
  tagline: "No equipment. Train anywhere.",
  description:
    "Ten body-weight exercises combined into five training days a week for four weeks. Sets, reps and session length increase each week.",
  equipment: ["No equipment", "Exercise mat (optional)", "Bench or chair"],
  exercises: [
    { id: "push-up", name: "Push-Up", muscle: "Chest", equipment: "None", baseMinutes: 5 },
    { id: "bodyweight-squat", name: "Bodyweight Squat", muscle: "Legs", equipment: "None", baseMinutes: 5, demo: "Hercules Squat" },
    { id: "reverse-lunge", name: "Reverse Lunge", muscle: "Legs", equipment: "None", baseMinutes: 5, demo: "Pistol Squat Jesus" },
    { id: "glute-bridge", name: "Glute Bridge", muscle: "Glutes", equipment: "Mat", baseMinutes: 4 },
    { id: "plank", name: "Plank", muscle: "Core", equipment: "Mat", baseMinutes: 3 },
    { id: "pike-push-up", name: "Pike Push-Up", muscle: "Shoulders", equipment: "None", baseMinutes: 5 },
    { id: "mountain-climbers", name: "Mountain Climbers", muscle: "Core", equipment: "None", baseMinutes: 4 },
    { id: "bird-dog", name: "Bird Dog", muscle: "Back", equipment: "Mat", baseMinutes: 4 },
    { id: "bench-dip", name: "Bench Dip", muscle: "Triceps", equipment: "Bench", baseMinutes: 4 },
    { id: "burpee", name: "Burpee", muscle: "Full body", equipment: "None", baseMinutes: 5 },
  ],
  days: [
    { title: "Upper Body Push", focus: "Chest, shoulders, triceps", items: [
      { exerciseId: "push-up", role: "core" }, { exerciseId: "pike-push-up", role: "core" },
      { exerciseId: "bench-dip", role: "core" }, { exerciseId: "plank", role: "accessory" },
      { exerciseId: "mountain-climbers", role: "accessory" } ] },
    { title: "Lower Body", focus: "Legs and glutes", items: [
      { exerciseId: "bodyweight-squat", role: "core" }, { exerciseId: "reverse-lunge", role: "core" },
      { exerciseId: "glute-bridge", role: "core" }, { exerciseId: "burpee", role: "accessory" },
      { exerciseId: "plank", role: "accessory" } ] },
    { title: "Core and Back", focus: "Core stability and posture", items: [
      { exerciseId: "plank", role: "core" }, { exerciseId: "bird-dog", role: "core" },
      { exerciseId: "glute-bridge", role: "core" }, { exerciseId: "mountain-climbers", role: "accessory" },
      { exerciseId: "bodyweight-squat", role: "accessory" } ] },
    { title: "Full Body", focus: "Whole-body strength", items: [
      { exerciseId: "burpee", role: "core" }, { exerciseId: "push-up", role: "core" },
      { exerciseId: "bodyweight-squat", role: "core" }, { exerciseId: "reverse-lunge", role: "accessory" },
      { exerciseId: "bird-dog", role: "accessory" }, { exerciseId: "bench-dip", role: "accessory" } ] },
    { title: "Conditioning", focus: "Endurance and core", items: [
      { exerciseId: "mountain-climbers", role: "core" }, { exerciseId: "burpee", role: "core" },
      { exerciseId: "pike-push-up", role: "core" }, { exerciseId: "bodyweight-squat", role: "accessory" },
      { exerciseId: "plank", role: "accessory" }, { exerciseId: "glute-bridge", role: "accessory" } ] },
  ],
  weekSchemes: [
    { sets: 3, reps: 10, minutesFactor: 1.0 },
    { sets: 3, reps: 12, minutesFactor: 1.1 },
    { sets: 4, reps: 10, minutesFactor: 1.2 },
    { sets: 4, reps: 12, minutesFactor: 1.3 },
  ],
};

const LDW: Program = {
  slug: "ldw",
  name: "LDW",
  fullName: "Loaded / Weights Program",
  tagline: "Barbells, dumbbells and cables.",
  description:
    "Ten weighted exercises combined into five training days a week for four weeks. Load goes up as reps come down from week 2 to week 4.",
  equipment: ["Barbell", "Dumbbells", "Cable machine", "Bench"],
  exercises: [
    { id: "barbell-bench-press", name: "Barbell Bench Press", muscle: "Chest", equipment: "Barbell, bench", baseMinutes: 7 },
    { id: "barbell-back-squat", name: "Barbell Back Squat", muscle: "Legs", equipment: "Barbell, rack", baseMinutes: 7, demo: "Hercules Squat" },
    { id: "romanian-deadlift", name: "Romanian Deadlift", muscle: "Hamstrings", equipment: "Barbell", baseMinutes: 7 },
    { id: "lat-pulldown", name: "Lat Pulldown", muscle: "Back", equipment: "Cable machine", baseMinutes: 6 },
    { id: "dumbbell-shoulder-press", name: "Dumbbell Shoulder Press", muscle: "Shoulders", equipment: "Dumbbells", baseMinutes: 6 },
    { id: "dumbbell-row", name: "Dumbbell Row", muscle: "Back", equipment: "Dumbbell, bench", baseMinutes: 6 },
    { id: "dumbbell-lunge", name: "Dumbbell Lunge", muscle: "Legs", equipment: "Dumbbells", baseMinutes: 6, demo: "Pistol Squat Jesus" },
    { id: "dumbbell-curl", name: "Dumbbell Biceps Curl", muscle: "Biceps", equipment: "Dumbbells", baseMinutes: 4 },
    { id: "triceps-pushdown", name: "Triceps Pushdown", muscle: "Triceps", equipment: "Cable machine", baseMinutes: 4 },
    { id: "cable-fly", name: "Cable Fly", muscle: "Chest", equipment: "Cable machine", baseMinutes: 5 },
  ],
  days: [
    { title: "Push", focus: "Chest, shoulders, triceps", items: [
      { exerciseId: "barbell-bench-press", role: "core" }, { exerciseId: "dumbbell-shoulder-press", role: "core" },
      { exerciseId: "cable-fly", role: "accessory" }, { exerciseId: "triceps-pushdown", role: "accessory" } ] },
    { title: "Pull", focus: "Back and biceps", items: [
      { exerciseId: "lat-pulldown", role: "core" }, { exerciseId: "dumbbell-row", role: "core" },
      { exerciseId: "romanian-deadlift", role: "accessory" }, { exerciseId: "dumbbell-curl", role: "accessory" } ] },
    { title: "Legs", focus: "Quads, hamstrings, glutes", items: [
      { exerciseId: "barbell-back-squat", role: "core" }, { exerciseId: "romanian-deadlift", role: "core" },
      { exerciseId: "dumbbell-lunge", role: "core" }, { exerciseId: "dumbbell-curl", role: "accessory" } ] },
    { title: "Upper Body", focus: "Chest, back, arms", items: [
      { exerciseId: "barbell-bench-press", role: "core" }, { exerciseId: "lat-pulldown", role: "core" },
      { exerciseId: "dumbbell-shoulder-press", role: "accessory" }, { exerciseId: "dumbbell-curl", role: "accessory" },
      { exerciseId: "triceps-pushdown", role: "accessory" } ] },
    { title: "Lower and Pull", focus: "Legs and back", items: [
      { exerciseId: "barbell-back-squat", role: "core" }, { exerciseId: "dumbbell-lunge", role: "core" },
      { exerciseId: "dumbbell-row", role: "core" }, { exerciseId: "romanian-deadlift", role: "accessory" },
      { exerciseId: "cable-fly", role: "accessory" } ] },
  ],
  weekSchemes: [
    { sets: 3, reps: 10, minutesFactor: 1.0 },
    { sets: 3, reps: 8, minutesFactor: 1.05 },
    { sets: 4, reps: 8, minutesFactor: 1.15 },
    { sets: 4, reps: 6, minutesFactor: 1.2 },
  ],
};

export const PROGRAMS: Program[] = [BW, LDW];

export function getProgram(slug: string): Program | undefined {
  return PROGRAMS.find((p) => p.slug === slug);
}

// ---------- derived schedule ----------

export type ScheduledExercise = {
  key: string; // unique within the program: w{week}-d{day}-{exerciseId}
  exercise: Exercise;
  role: Role;
  sets: number;
  reps: number;
  minutes: number;
};

export type ScheduledDay = {
  week: number; // 1..4
  day: number; // 1..7 inside the week
  number: number; // 1..28 across the program
  rest: boolean;
  title: string;
  focus: string;
  exercises: ScheduledExercise[];
  coreMinutes: number;
  optionalMinutes: number;
  totalMinutes: number;
};

export function buildSchedule(program: Program): ScheduledDay[] {
  const byId = new Map(program.exercises.map((e) => [e.id, e]));
  const days: ScheduledDay[] = [];
  for (let week = 1; week <= WEEKS; week++) {
    const scheme = program.weekSchemes[week - 1];
    for (let day = 1; day <= DAYS_PER_WEEK; day++) {
      const number = (week - 1) * DAYS_PER_WEEK + day;
      if (day > WORKOUT_DAYS_PER_WEEK) {
        days.push({ week, day, number, rest: true, title: "Rest day", focus: "Recover and stretch lightly",
          exercises: [], coreMinutes: 0, optionalMinutes: 0, totalMinutes: 0 });
        continue;
      }
      const tpl = program.days[day - 1];
      const exercises: ScheduledExercise[] = tpl.items.map(({ exerciseId, role }) => {
        const exercise = byId.get(exerciseId);
        if (!exercise) throw new Error(`Unknown exercise ${exerciseId} in ${program.slug}`);
        return {
          key: `w${week}-d${day}-${exerciseId}`,
          exercise, role,
          sets: scheme.sets, reps: scheme.reps,
          minutes: Math.round(exercise.baseMinutes * scheme.minutesFactor),
        };
      });
      const core = exercises.filter((e) => e.role === "core").reduce((s, e) => s + e.minutes, 0);
      const opt = exercises.filter((e) => e.role === "accessory").reduce((s, e) => s + e.minutes, 0);
      days.push({ week, day, number, rest: false, title: tpl.title, focus: tpl.focus,
        exercises, coreMinutes: core, optionalMinutes: opt, totalMinutes: core + opt });
    }
  }
  return days;
}

export function minutesRange(days: ScheduledDay[]): [number, number] {
  const m = days.filter((d) => !d.rest).map((d) => d.totalMinutes);
  return [Math.min(...m), Math.max(...m)];
}
