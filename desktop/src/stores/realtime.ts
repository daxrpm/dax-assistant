import { shutdownChatStores } from "../hooks/useChatSocket";
import { logStore } from "../hooks/useLogStream";
import { voiceStore } from "../hooks/useVoiceSocket";

export function shutdownRealtimeStores() {
  voiceStore.shutdown();
  logStore.shutdown();
  shutdownChatStores();
}
