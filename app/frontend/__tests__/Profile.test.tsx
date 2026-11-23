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

function setup(props: any = {}) {
  mockApi.mockImplementation((path: string, options?: any) => {
    if (path === "/equipment") {
      return Promise.resolve(equipment);
    }

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
      {...props}
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

    expect(
      await screen.findByRole("heading", { name: /Your goal/i })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", { name: /Experience level/i })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", { name: /Schedule/i })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", { name: /Equipment/i })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", { name: /Limitations/i })
    ).toBeInTheDocument();

    expect(await screen.findByText("Dumbbells")).toBeInTheDocument();
  });

  test("allows users to select a fitness goal", async () => {
    setup();

    const goal = screen.getByRole("button", {
      name: /Build muscle/i,
    });

    fireEvent.click(goal);

    expect(goal).toHaveAttribute("aria-pressed", "true");
  });

  test("allows users to select their experience level", async () => {
    setup();

    const level = screen.getByRole("button", {
      name: /intermediate/i,
    });

    fireEvent.click(level);

    expect(level).toHaveAttribute("aria-pressed", "true");
  });

  test("allows users to change their workout schedule", async () => {
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

    const knee = screen.getByRole("button", {
      name: "Knee",
    });

    fireEvent.click(dumbbells);
    fireEvent.click(knee);

    expect(dumbbells).toHaveAttribute("aria-pressed", "true");
    expect(knee).toHaveAttribute("aria-pressed", "true");
  });

  test("saves the selected profile information", async () => {
    setup();

    // Wait for the existing profile to load, otherwise it overwrites the clicks below.
    await screen.findByText(/Go to Programs/);

    fireEvent.click(
      screen.getByRole("button", { name: /Build strength/i })
    );

    fireEvent.click(
      screen.getByRole("button", { name: /beginner/i })
    );

    fireEvent.click(
      screen.getByRole("button", { name: "3" })
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Dumbbells" })
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Save changes" })
    );

    await waitFor(() => {
      expect(mockApi).toHaveBeenCalledWith(
        "/profile",
        expect.objectContaining({
          method: "PUT",
          body: expect.any(String),
        })
      );
    });

    const saveCall = mockApi.mock.calls.find(
      (call: any[]) =>
        call[0] === "/profile" &&
        call[1]?.method === "PUT"
    );

    expect(saveCall).toBeDefined();

    const savedData = JSON.parse(saveCall[1].body);

    expect(savedData.goals).toEqual(["Build strength"]);
    expect(savedData.experience_level).toBe("beginner");
    expect(savedData.days_per_week).toBe(3);
    expect(savedData.equipment_ids).toEqual([1]);

    expect(
      await screen.findByText("All changes saved.")
    ).toBeInTheDocument();
  });

  test("displays an error when saving fails", async () => {
    setup();

    // Wait for the initial load, then make saving fail.
    await screen.findByText(/Go to Programs/);

    mockApi.mockImplementation((path: string, options?: any) => {
      if (options?.method === "PUT") {
        return Promise.reject(new Error("Unable to save profile"));
      }
      return Promise.resolve(existingProfile);
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Save changes" })
    );

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent("Unable to save profile");
  });

  test("redirects after first-time profile setup", async () => {
    setup({
      kicker: "Setup",
      title: "Set up your profile",
      lead: "Complete your profile.",
      submitLabel: "Save profile",
      afterSaveHref: "/profile",
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Save profile" })
    );

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/profile");
    });
  });
});