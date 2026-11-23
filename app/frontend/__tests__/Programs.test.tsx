
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ProgramLibraryPage from "../app/programs/page";
import { api, getToken, useAuth } from "../lib/auth";

jest.mock("../lib/auth", () => ({
  api: jest.fn(),
  getToken: jest.fn(),
  useAuth: jest.fn(() => ({
    user: { id: "user-1" },
    loading: false,
  })),
}));

jest.mock("../components/Navbar", () => {
  return function MockNavbar() {
    return <nav>Navbar</nav>;
  };
});

const mockApi = api as jest.Mock;
const mockGetToken = getToken as jest.Mock;
const mockUseAuth = useAuth as jest.Mock;

const program = {
  id: 1,
  name: "Strength Builder",
  goal: "Build strength",
  experience_level: "beginner",
  length_weeks: 1,
  description: "A beginner strength training program.",
};

const session = {
  id: 10,
  name: "Upper Body",
  program_id: 1,
  total_minutes: 45,
  exercise_count: 1,
  muscle_groups: ["Chest"],
};

const sessionDetail = {
  ...session,
  guidance: "Focus on proper form.",
  exercises: [
    {
      id: 100,
      exercise_id: 200,
      name: "Bench Press",
      role: "core",
      sets: 3,
      reps: 10,
      minutes: 20,
      equipment: ["Barbell"],
      primary_muscles: ["Chest"],
      video_url: null,
    },
  ],
};

function setup(records: any[] = []) {
  mockGetToken.mockReturnValue("test-token");

  mockUseAuth.mockReturnValue({
    user: { id: "user-1" },
    loading: false,
  });

  mockApi.mockImplementation((path: string, options?: any) => {
    if (path.startsWith("/programs?")) {
      return Promise.resolve({ items: [program], total: 1 });
    }

    if (path.startsWith("/workout-sessions?")) {
      return Promise.resolve({ items: [session], total: 1 });
    }

    if (path === "/workout-sessions/10") {
      return Promise.resolve(sessionDetail);
    }

    if (path.startsWith("/workout-records?")) {
      return Promise.resolve({ items: records, total: records.length });
    }

    if (path === "/workout-records" && options?.method === "POST") {
      return Promise.resolve({});
    }

    return Promise.reject(new Error("Unexpected API request: " + path));
  });

  return render(<ProgramLibraryPage />);
}

describe("Programs Page", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    Element.prototype.scrollIntoView = jest.fn();

    mockUseAuth.mockReturnValue({
      user: { id: "user-1" },
      loading: false,
    });
  });

  test("displays the programs heading and available program", async () => {
    setup();

    expect(
      await screen.findByText("Strength Builder"),
    ).toBeInTheDocument();

    expect(screen.getByText("Build strength · beginner")).toBeInTheDocument();
    expect(screen.getByText("1 weeks")).toBeInTheDocument();
  });

  test("displays a message when no programs exist", async () => {
    mockGetToken.mockReturnValue(null);

    mockApi.mockImplementation((path: string) => {
      if (path.startsWith("/programs?")) {
        return Promise.resolve({ items: [], total: 0 });
      }

      if (path.startsWith("/workout-sessions?")) {
        return Promise.resolve({ items: [], total: 0 });
      }

      return Promise.resolve({ items: [], total: 0 });
    });

    render(<ProgramLibraryPage />);

    expect(
      await screen.findByText("No programs are in the database yet."),
    ).toBeInTheDocument();
  });

  test("displays an error when programs fail to load", async () => {
    mockApi.mockRejectedValue(new Error("Could not load programs"));

    render(<ProgramLibraryPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not load programs",
    );
  });

  test("opens a program and displays its workout", async () => {
    setup();

    await screen.findByText("Strength Builder");

    fireEvent.click(
      screen.getByRole("link", { name: /View program/i }),
    );

    expect(await screen.findByText("Bench Press")).toBeInTheDocument();
    expect(screen.getByText("0/5 days")).toBeInTheDocument();
  });

  test("marks a workout complete and updates progress", async () => {
    setup();

    await screen.findByText("Strength Builder");

    fireEvent.click(
      screen.getByRole("link", { name: /View program/i }),
    );

    await screen.findByText("Bench Press");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Mark Day 1 As Complete",
      }),
    );

    await waitFor(() => {
      expect(mockApi).toHaveBeenCalledWith(
        "/workout-records",
        expect.objectContaining({
          method: "POST",
          body: expect.any(String),
        }),
      );
    });

    expect(await screen.findByText("1/5 days")).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Day 1 Logged ✓" }),
    ).toBeDisabled();
  });

  test("restores previously completed workout progress", async () => {
    setup([
      {
        id: 1,
        workout_session_id: 10,
        performed_at: "2026-11-20T12:00:00",
      },
    ]);

    await screen.findByText("Strength Builder");

    fireEvent.click(
      screen.getByRole("link", { name: /View program/i }),
    );

    expect(await screen.findByText("1/5 days")).toBeInTheDocument();

    expect(
      await screen.findByRole("button", { name: "Day 1 Logged ✓" }),
    ).toBeDisabled();
  });
});
