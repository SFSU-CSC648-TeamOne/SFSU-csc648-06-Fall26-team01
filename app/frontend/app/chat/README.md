# Ascenda chatbot (widget + /chat page)

1. Copy this `chat/` folder to `app/frontend/app/chat/`.
2. In your existing `app/layout.tsx`, wrap the body content and add the widget:

   import ChatProvider from "./chat/ChatProvider";
   import ChatWidget from "./chat/ChatWidget";
   ...
   <ChatProvider>
     {/* your header / sidebar / children */}
     {children}
     <ChatWidget />
   </ChatProvider>

3. Add "AI Chat" -> /chat to the sidebar menu (decision pending with the team).
4. `ChatWidget.tsx` HIDDEN list: change if your signed-out routes differ.
5. `page.tsx`: replace USER_NAME with the signed-in user's first name (GET /api/auth/me).
6. `chatApi.ts`: replace the placeholder with the real /api/chat/* calls. Conversations are kept in
   localStorage for now; once the backend saves them, load them from the server in ChatProvider.
7. `.fullPage` height assumes a 54px header; adjust to your header.
