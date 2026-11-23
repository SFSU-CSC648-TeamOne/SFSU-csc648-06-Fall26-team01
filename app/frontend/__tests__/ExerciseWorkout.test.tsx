import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import ExerciseWorkout from "../app/programs/[slug]/exercise/[key]/ExerciseWorkout";
import { api, useAuth } from "../lib/auth";
import { useRouter } from "next/navigation";
import { useProgramPrescription } from "../app/programs/useProgramPrescription";

jest.mock("../lib/auth", () => ({
  api: jest.fn(),
  useAuth: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

jest.mock("next/link", () => {
  return function MockLink({ children, href }: any) {
    return <a href={href}>{children}</a>;
  };
});

jest.mock("next/dynamic", () => () => {
  return function MockDynamic() {
    return null;
  };
});

jest.mock("../components/Navbar", () => {
  return function MockNavbar() {
    return <nav>Navbar</nav>;
  };
});

jest.mock("../app/programs/useProgramPrescription", () => ({
  useProgramPrescription: jest.fn(),
}));

jest.mock("../app/programs/programsData", () => ({
  getProgram: jest.fn(() => ({
    name: "Strength Builder",
  })),
  buildSchedule: jest.fn(() => [
    {
      week: 1,
      number: 1,
      exercises: [
        {
          key: "push-up",
          role: "core",
          sets: 2,
          reps: 2,
          exercise: {
            id: "push-up",
            name: "Push Up",
            muscle: "Chest",
            equipment: "None",
          },
        },
      ],
    },
  ]),
  CATALOG_IDS: { "push-up": 101 },
  DUMMY_MODELS: {},
}));

jest.mock("../lib/programProgress", () => ({
  readProgress: jest.fn(() => ({ checked: {} })),
  writeProgress: jest.fn(),
  writeLast: jest.fn(),
}));

const mockApi = api as jest.Mock;
const mockAuth = useAuth as jest.Mock;
const mockRouter = useRouter as jest.Mock;
const mockPrescription = useProgramPrescription as jest.Mock;

const mockPush = jest.fn();

function setup() {
  mockAuth.mockReturnValue({
    user: null,
    loading: false,
  });

  mockRouter.mockReturnValue({
    push: mockPush,
  });

  mockPrescription.mockReturnValue({
    days: [
      {
        week: 1,
        number: 1,
        exercises: [
          {
            key: "push-up",
            role: "core",
            sets: 2,
            reps: 2,
            exercise: {
              id: "push-up",
              name: "Push Up",
              muscle: "Chest",
              equipment: "None",
            },
          },
        ],
      },
    ],
    baseline: null,
    loading: false,
    error: null,
  });

  mockApi.mockImplementation((path: string) => {
    if (path.startsWith("/exercises?q=")) {
      return Promise.resolve({
        items: [{ id: 55, name: "Push Up" }],
      });
    }

    if (path === "/exercises/55/model") {
      return Promise.resolve({});
    }

    if (path === "/exercises/55/scans") {
      return Promise.resolve([]);
    }

    if (path === "/exercises/101") {
      return Promise.resolve({});
    }

    return Promise.resolve({});
  });

  return render(
    <ExerciseWorkout slug="strength-builder" exKey="push-up" />
  );
}

// Lets the exercise lookup (api -> setCatalogExerciseId) finish before the test clicks anything.
async function waitForCatalogLookup() {
  await waitFor(() => {
    expect(mockApi).toHaveBeenCalledWith(
      expect.stringContaining("/exercises?q=")
    );
  });
  await act(async () => {});
}

// Completes one set of 2 reps: +1 REP twice, then Save set.
function completeSetAndSave() {
  fireEvent.click(screen.getByRole("button", { name: "+1 REP" }));
  fireEvent.click(screen.getByRole("button", { name: "+1 REP" }));
  fireEvent.click(screen.getByRole("button", { name: "Save set" }));
}

// Completes the last set (2 reps) without saving; "Mark done" saves it.
function completeLastSet() {
  fireEvent.click(screen.getByRole("button", { name: "+1 REP" }));
  fireEvent.click(screen.getByRole("button", { name: "+1 REP" }));
}

describe("Exercise Workout", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("displays exercise information", async () => {
    setup();

    expect(
      await screen.findByRole("heading", { name: "Push Up" })
    ).toBeInTheDocument();
    expect(screen.getByText(/2 sets × 2 reps/)).toBeInTheDocument();
    expect(screen.getByText(/Chest/)).toBeInTheDocument();
  });

  test("starts, pauses, resumes, and resets the timer", async () => {
    jest.useFakeTimers();
    setup();

    fireEvent.click(screen.getByRole("button", { name: "Start" }));
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();

    act(() => {
      jest.advanceTimersByTime(1200);
    });
    expect(screen.getByRole("timer")).toHaveTextContent("00:01");

    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(screen.getByRole("timer")).toHaveTextContent("00:00");
  });

  test("counts reps up and lets the user correct the count", () => {
    setup();

    const reps = screen.getByRole("status");

    fireEvent.click(screen.getByRole("button", { name: "+1 REP" }));
    expect(reps).toHaveTextContent("1 / 2 reps");

    fireEvent.change(screen.getByLabelText("Actual repetitions completed"), {
      target: { value: "0" },
    });
    expect(reps).toHaveTextContent("0 / 2 reps");
  });

  test("marks the set complete after reaching the target reps", () => {
    setup();

    fireEvent.click(screen.getByRole("button", { name: "+1 REP" }));
    fireEvent.click(screen.getByRole("button", { name: "+1 REP" }));

    expect(screen.getByRole("button", { name: "SET COMPLETE" })).toBeDisabled();
  });

  test("advances to the next set after saving a set", () => {
    setup();

    completeSetAndSave();

    expect(screen.getByText("Set 2 of 2")).toBeInTheDocument();
  });

  test("skipping a set advances to the next set", () => {
    setup();

    fireEvent.click(screen.getByRole("button", { name: "Skip set" }));

    expect(screen.getByText("Set 2 of 2")).toBeInTheDocument();
  });

  test("saves completed sets and navigates after finishing", async () => {
    setup();
    await waitForCatalogLookup();

    completeSetAndSave();
    completeLastSet();

    fireEvent.click(screen.getByRole("button", { name: /Mark done/i }));

    await waitFor(() => {
      expect(mockApi).toHaveBeenCalledWith(
        "/workout-records",
        expect.objectContaining({ method: "POST", body: expect.any(String) })
      );
    });

    const call = mockApi.mock.calls.find(
      (c: any[]) => c[0] === "/workout-records"
    );
    const body = JSON.parse(call[1].body);
    expect(body.program_slug).toBe("strength-builder");
    expect(body.entries).toHaveLength(2);
    expect(body.entries[0]).toMatchObject({
      exercise_id: 55,
      set_number: 1,
      reps: 2,
      status: "completed",
    });

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/programs/strength-builder");
    });
  });

  test("requires at least one completed set before finishing", async () => {
    setup();
    await waitForCatalogLookup();

    fireEvent.click(screen.getByRole("button", { name: /Mark done/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Complete at least one set before finishing."
    );
    expect(mockApi).not.toHaveBeenCalledWith(
      "/workout-records",
      expect.anything()
    );
  });

  test("displays an error when workout saving fails", async () => {
    setup();
    await waitForCatalogLookup();

    // Make only the save fail (the exercise lookup already finished).
    mockApi.mockImplementation((path: string) => {
      if (path === "/workout-records") {
        return Promise.reject(new Error("Workout save failed"));
      }
      return Promise.resolve({});
    });

    completeSetAndSave();
    completeLastSet();

    fireEvent.click(screen.getByRole("button", { name: /Mark done/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Workout save failed"
    );
    expect(mockPush).not.toHaveBeenCalled();
  });
});