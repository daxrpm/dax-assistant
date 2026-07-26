package com.dax.assistant.ui.conversations

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dax.assistant.data.conversations.ChatMessage
import com.dax.assistant.data.conversations.ChatRepository
import com.dax.assistant.data.conversations.ConversationApi
import com.dax.assistant.data.conversations.ConversationApiResult
import com.dax.assistant.data.conversations.ConversationChatState
import com.dax.assistant.data.conversations.ConversationSummary
import com.dax.assistant.audio.Speaker
import com.dax.assistant.data.transport.ConnectionState
import com.dax.assistant.preferences.AppPreferences
import dagger.hilt.android.lifecycle.HiltViewModel
import java.time.Instant
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ConversationsUiState(
    val conversations: List<ConversationSummary> = emptyList(),
    val selectedConversationId: String? = null,
    val chat: ConversationChatState? = null,
    val search: String = "",
    val loadingList: Boolean = false,
    val loadingChat: Boolean = false,
    val deletingId: String? = null,
    val error: String? = null,
    val connection: ConnectionState = ConnectionState.Disconnected,
)

@HiltViewModel
class ConversationsViewModel @Inject constructor(
    private val api: ConversationApi,
    private val repository: ChatRepository,
    private val speaker: Speaker,
    private val preferences: AppPreferences,
) : ViewModel() {
    private val _state = MutableStateFlow(ConversationsUiState())
    val state: StateFlow<ConversationsUiState> = _state.asStateFlow()
    private var sessionId: String? = null
    private var chatJob: Job? = null
    private var requestGeneration = 0
    // Ids already accounted for, so opening a conversation reads none of its
    // history aloud — only what arrives while you are looking at it.
    private val spokenIds = mutableSetOf<String>()
    private var speakJob: Job? = null

    init {
        refresh()
        viewModelScope.launch {
            repository.connection.collect { connection -> _state.update { it.copy(connection = connection) } }
        }
    }

    fun setSearch(value: String) = _state.update { it.copy(search = value) }

    fun refresh() {
        _state.update { it.copy(loadingList = true, error = null) }
        viewModelScope.launch {
            when (val result = api.list()) {
                is ConversationApiResult.Success -> _state.update {
                    it.copy(conversations = result.value, loadingList = false)
                }
                is ConversationApiResult.Failed -> _state.update {
                    it.copy(loadingList = false, error = result.reason)
                }
            }
        }
    }

    fun select(conversation: ConversationSummary) {
        if (_state.value.selectedConversationId == conversation.id) return
        val generation = ++requestGeneration
        _state.update { it.copy(loadingChat = true, error = null) }
        viewModelScope.launch {
            when (val result = api.get(conversation.id)) {
                is ConversationApiResult.Success -> {
                    if (generation != requestGeneration) return@launch
                    val detail = result.value
                    bind(
                        detail.sessionKey,
                        detail.messages.map {
                            ChatMessage(it.id, it.role, it.content, it.timestamp)
                        },
                    )
                    _state.update {
                        it.copy(selectedConversationId = conversation.id, loadingChat = false)
                    }
                }
                is ConversationApiResult.Failed -> if (generation == requestGeneration) {
                    _state.update { it.copy(loadingChat = false, error = result.reason) }
                }
            }
        }
    }

    fun newConversation() {
        requestGeneration++
        bind("android-chat-${UUID.randomUUID()}", emptyList())
        _state.update { it.copy(selectedConversationId = null, loadingChat = false, error = null) }
    }

    fun closeDetail() {
        requestGeneration++
        unbind()
        _state.update { it.copy(selectedConversationId = null, chat = null, loadingChat = false) }
    }

    fun delete(conversation: ConversationSummary) {
        _state.update { it.copy(deletingId = conversation.id, error = null) }
        viewModelScope.launch {
            when (val result = api.delete(conversation.id)) {
                is ConversationApiResult.Success -> {
                    val active = _state.value.chat?.sessionId == conversation.sessionKey
                    _state.update {
                        it.copy(
                            conversations = it.conversations.filterNot { item -> item.id == conversation.id },
                            deletingId = null,
                        )
                    }
                    if (active) newConversation()
                }
                is ConversationApiResult.Failed -> _state.update {
                    it.copy(deletingId = null, error = result.reason)
                }
            }
        }
    }

    fun send(content: String): Boolean = sessionId?.let { repository.send(it, content) } ?: false

    fun resolveApproval(approvalId: String, decision: String): Boolean =
        sessionId?.let { repository.resolveApproval(it, approvalId, decision) } ?: false

    fun expireApproval(approvalId: String) {
        sessionId?.let { repository.expireApproval(it, approvalId) }
    }

    private fun bind(nextSessionId: String, messages: List<ChatMessage>) {
        unbind()
        val flow = repository.retain(nextSessionId, messages)
        if (flow == null) {
            _state.update { it.copy(error = "Too many active conversations", loadingChat = false) }
            return
        }
        sessionId = nextSessionId
        // Everything already in the thread counts as heard.
        spokenIds.clear()
        messages.forEach { spokenIds.add(it.id) }
        chatJob = viewModelScope.launch {
            flow.collect { chat ->
                _state.update { it.copy(chat = chat) }
                speakLatestReply(chat.messages)
            }
        }
    }

    /** Read the newest finished assistant turn aloud, at most once. */
    private fun speakLatestReply(messages: List<ChatMessage>) {
        val latest = messages.lastOrNull { it.role == "assistant" && !it.pending && !it.failed }
        val isNew = latest != null && latest.id !in spokenIds
        // Mark finished messages seen even when speaking is off, so switching it
        // on mid-conversation does not suddenly recite the backlog. Pending ones
        // are deliberately excluded: a streamed reply arrives pending first and
        // is finalised under the same id, so marking it here would mean the
        // finished answer is never spoken at all.
        messages.forEach { if (!it.pending) spokenIds.add(it.id) }
        if (latest == null || !isNew) return
        if (!preferences.state.value.speakChatReplies) return
        if (latest.content.isBlank()) return

        // A new reply replaces whatever is still being spoken; two overlapping
        // answers are worse than a truncated one.
        speakJob?.cancel()
        speaker.stop()
        speakJob = viewModelScope.launch {
            runCatching { speaker.speak(latest.content) }
        }
    }

    /** Silence the current reply — used by the UI's stop control. */
    fun stopSpeaking() {
        speakJob?.cancel()
        speakJob = null
        speaker.stop()
    }

    fun setSpeakReplies(enabled: Boolean) {
        preferences.setSpeakChatReplies(enabled)
        if (!enabled) stopSpeaking()
    }

    private fun unbind() {
        chatJob?.cancel()
        chatJob = null
        stopSpeaking()
        spokenIds.clear()
        sessionId?.let(repository::release)
        sessionId = null
    }

    override fun onCleared() {
        unbind()
        super.onCleared()
    }
}
