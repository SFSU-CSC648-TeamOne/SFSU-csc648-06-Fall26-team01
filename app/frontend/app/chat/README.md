# Ascenda chatbot (widget + /chat page)

The chat feature is already wired into the application. The backend uses Gemini
when `GEMINI_API_KEY` is configured.

1. In `app/layout.tsx`, keep the provider and widget around the page content:

   import ChatProvider from "./chat/ChatProvider";
   import ChatWidget from "./chat/ChatWidget";
   ...
   <ChatProvider>
     {/* your header / sidebar / children */}
     {children}
     <ChatWidget />
   </ChatProvider>

2. `ChatWidget.tsx` hides the floating widget on `/chat`, where the full-page
   experience is rendered.
3. `chatApi.ts` calls the persisted `/api/chat/*` endpoints.
4. `.fullPage` height assumes a 54px header; adjust to your header if needed.
