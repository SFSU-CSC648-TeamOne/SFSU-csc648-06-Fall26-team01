import "./globals.css";
import ChatProvider from "./chat/ChatProvider";
import ChatWidget from "./chat/ChatWidget";

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <ChatProvider>
          {children}
          <ChatWidget />
        </ChatProvider>
      </body>
    </html>
  );
}
