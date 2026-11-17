type ProgressPoint = {
  date: string;
  prescribed: number | null;
  actual: number | null;
};

type ExerciseProgressChartProps = {
  exerciseName: string;
  points: ProgressPoint[];
};