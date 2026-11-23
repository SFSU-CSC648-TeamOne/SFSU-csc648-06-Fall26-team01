
import { fireEvent, render, screen } from "@testing-library/react";
import ChatPanel, { HistoryList } from "../app/chat/ChatPanel";
import { useChat } from "../app/chat/ChatProvider";

jest.mock("../app/chat/ChatProvider", () => ({
  useChat: jest.fn(),
}));

const mockUseChat = useChat as jest.Mock;

const mockSend = jest.fn();
const mockNewChat = jest.fn();
const mockSelect = jest.fn();
const mockRemove = jest.fn();

const conversations = [
  { id: "chat-1", title: "Workout advice" },
  { id: "chat-2", title: "Nutrition questions" },
];

const active = {
  id: "chat-1",
  messages: [
    { id: "msg-1", role: "user", content: "How do I build muscle?" },
    {
      id: "msg-2",
      role: "assistant",
      content: "Start with consistent strength training.",
    },
  ],
};

function setupChat(overrides = {}) {
  mockUseChat.mockReturnValue({
    active,
    conversations,
    send: mockSend,
    sending: false,
    error: null,
    select: mockSelect,
    newChat: mockNewChat,
    remove: mockRemove,
    ...overrides,
  });
}

beforeEach(() => {
  jest.clearAllMocks();

  window.HTMLElement.prototype.scrollIntoView = jest.fn();

  setupChat();
});

describe("ChatPanel", () => {
  test("renders the message input and send button", () => {
    render(<ChatPanel />);

    expect(screen.getByLabelText("Message")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
  });

  test("displays existing chat messages", () => {
    render(<ChatPanel />);

    expect(screen.getByText("How do I build muscle?")).toBeInTheDocument();
    expect(
      screen.getByText("Start with consistent strength training."),
    ).toBeInTheDocument();
  });

  test("displays the default greeting when there are no messages", () => {
    setupChat({
      active: { id: "chat-1", messages: [] },
    });

    render(<ChatPanel />);

    expect(
      screen.getByText("Ask me about exercises, programs or your training."),
    ).toBeInTheDocument();
  });

  test("sends a message when the user submits the form", () => {
    render(<ChatPanel />);

    const input = screen.getByLabelText("Message");

    fireEvent.change(input, {
      target: { value: "Give me a workout plan" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(mockSend).toHaveBeenCalledWith("Give me a workout plan");
    expect(input).toHaveValue("");
  });

  test("disables the send button when the input is empty", () => {
    render(<ChatPanel />);

    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  test("disables the send button when the input contains only spaces", () => {
    render(<ChatPanel />);

    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "   " },
    });

    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  test("displays a loading indicator while sending", () => {
    setupChat({ sending: true });

    render(<ChatPanel />);

    expect(screen.getByText("···")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  test("displays an error message when chat fails", () => {
    setupChat({ error: "Unable to send message" });

    render(<ChatPanel />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Unable to send message",
    );
  });

  test("displays a custom greeting when provided", () => {
    setupChat({
      active: { id: "chat-1", messages: [] },
    });

    render(<ChatPanel greeting={<p>Welcome back!</p>} />);

    expect(screen.getByText("Welcome back!")).toBeInTheDocument();
  });
});

describe("HistoryList", () => {
  test("displays the chat history heading", () => {
    render(<HistoryList />);

    expect(screen.getByText("Chat history")).toBeInTheDocument();
    expect(screen.getByText("Workout advice")).toBeInTheDocument();
    expect(screen.getByText("Nutrition questions")).toBeInTheDocument();
  });

  test("displays a message when there are no conversations", () => {
    setupChat({ conversations: [] });

    render(<HistoryList />);

    expect(screen.getByText("No conversations yet.")).toBeInTheDocument();
  });

  test("creates a new chat and calls onPick", () => {
    const onPick = jest.fn();

    render(<HistoryList onPick={onPick} />);

    fireEvent.click(screen.getByRole("button", { name: "+ New chat" }));

    expect(mockNewChat).toHaveBeenCalledTimes(1);
    expect(onPick).toHaveBeenCalledTimes(1);
  });

  test("selects a conversation and calls onPick", () => {
    const onPick = jest.fn();

    render(<HistoryList onPick={onPick} />);

    fireEvent.click(screen.getByRole("button", { name: "Workout advice" }));

    expect(mockSelect).toHaveBeenCalledWith("chat-1");
    expect(onPick).toHaveBeenCalledTimes(1);
  });

  test("deletes a conversation", () => {
    render(<HistoryList />);

    fireEvent.click(
      screen.getByRole("button", { name: "Delete Workout advice" }),
    );

    expect(mockRemove).toHaveBeenCalledWith("chat-1");
  });
});
