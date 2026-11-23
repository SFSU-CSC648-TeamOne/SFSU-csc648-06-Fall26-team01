
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ProfileForm from "../components/ProfileForm";
import { api } from "../lib/auth";
import { useRouter } from "next/navigation";

jest.mock("../lib/auth", () => ({
  api: jest.fn(),
  displayName: jest.fn(() => "Test User"),
}));

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

jest.mock("next/link", () => {
  return function MockLink({ children, href }: any) {
    return <a href={href}>{children}</a>;
  };
});

const mockApi = api as jest.Mock;
const mockReplace = jest.fn();

const equipment = [
  { id: 1, name: "Dumbbells" },
  { id: 2, name: "Resistance Bands" },
];

const existingProfile = {
  goals: [],
  experience_level: null,
  days_per_week: 4,
  session_minutes: 45,
  physical_constraints: null,
  equipment_ids: [],
};

function setup() {
  mockApi.mockImplementation((path: string, options?: any) => {
    if (path === "/equipment") return Promise.resolve(equipment);

    if (path === "/profile" && options?.method === "PUT") {
      return Promise.resolve({});
    }

    return Promise.resolve(existingProfile);
  });

  return render(
    <ProfileForm
      user={null}
      kicker="Profile"
      title="Your profile"
      lead="Update your fitness information."
      submitLabel="Save changes"
    />
  );
}

describe("Profile Form", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({
      replace: mockReplace,
    });
  });

  test("displays all five profile sections", async () => {
    setup();

    expect(screen.getByText("Your goal")).toBeInTheDocument();
    expect(screen.getByText("Experience level")).toBeInTheDocument();
    expect(screen.getByText("Schedule")).toBeInTheDocument();
    expect(screen.getByText("Equipment")).toBeInTheDocument();
    expect(screen.getByText("Limitations")).toBeInTheDocument();

    expect(await screen.findByText("Dumbbells")).toBeInTheDocument();
  });

  test("allows users to select a fitness goal", () => {
    setup();

    const goal = screen.getByRole("button", { name: /Build muscle/i });
    fireEvent.click(goal);

    expect(goal).toHaveAttribute("aria-pressed", "true");
  });

  test("allows users to select their experience level", () => {
    setup();

    const level = screen.getByRole("button", { name: /intermediate/i });
    fireEvent.click(level);

    expect(level).toHaveAttribute("aria-pressed", "true");
  });

  test("allows users to change their workout schedule", () => {
    setup();

    const days = screen.getByRole("button", { name: "3" });
    const minutes = screen.getByRole("button", { name: "60" });

    fireEvent.click(days);
    fireEvent.click(minutes);

    expect(days).toHaveAttribute("aria-pressed", "true");
    expect(minutes).toHaveAttribute("aria-pressed", "true");
  });

  test("allows users to select equipment and limitations", async () => {
    setup();

    const dumbbells = await screen.findByRole("button", {
      name: "Dumbbells",
    });
    const knee = screen.getByRole("button", { name: "Knee" });

    fireEvent.click(dumbbells);
    fireEvent.click(knee);

    expect(dumbbells).toHaveAttribute("aria-pressed", "true");
    expect(knee).toHaveAttribute("aria-pressed", "true");
  });

  test("saves the selected profile information", async () => {
    setup();

    fireEvent.click(screen.getByRole("button", { name: /Build strength/i }));
    fireEvent.click(screen.getByRole("button", { name: /beginner/i }));
    fireEvent.click(screen.getByRole("button", { name: "3" }));

    fireEvent.click(
      await screen.findByRole("button", { name: "Dumbbells" })
    );

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(mockApi).toHaveBeenCalledWith(
        "/profile",
        expect.objectContaining({
          method: "PUT",
          body: expect.any(String),
        })
      );
    });

    const savedData = JSON.parse(
      mockApi.mock.calls.find(
        (call: any[]) => call[0] === "/profile" && call[1]?.method === "PUT"
      )[1].body
    );

    expect(savedData.goals).toEqual(["Build strength"]);
    expect(savedData.experience_level).toBe("beginner");
    expect(savedData.days_per_week).toBe(3);
    expect(savedData.equipment_ids).toEqual([1]);

    expect(await screen.findByText("All changes saved.")).toBeInTheDocument();
  });

  test("displays an error when saving fails", async () => {
    mockApi.mockImplementation((path: string, options?: any) => {
      if (path === "/equipment") return Promise.resolve(equipment);

      if (options?.method === "PUT") {
        return Promise.reject(new Error("Unable to save profile"));
      }

      return Promise.resolve(existingProfile);
    });

    render(
      <ProfileForm
        user={null}
        kicker="Profile"
        title="Your profile"
        lead="Update your fitness information."
        submitLabel="Save changes"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to save profile"
    );
  });

  test("redirects after first-time profile setup", async () => {
    setup();

    render(
      <ProfileForm
        user={null}
        kicker="Setup"
        title="Set up your profile"
        lead="Complete your profile."
        submitLabel="Save profile"
        afterSaveHref="/profile"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/profile");
    });
  });
});
