package com.dax.assistant.ui.conversations

import com.dax.assistant.audio.Speaker
import com.dax.assistant.data.conversations.ChatMessage
import com.dax.assistant.data.conversations.ChatRepository
import com.dax.assistant.data.conversations.ConversationApi
import com.dax.assistant.data.conversations.ConversationApiResult
import com.dax.assistant.data.conversations.ConversationChatState
import com.dax.assistant.data.conversations.ConversationDetail
import com.dax.assistant.data.conversations.ConversationMessage
import com.dax.assistant.data.conversations.ConversationSummary
import com.dax.assistant.data.transport.ConnectionState
import com.dax.assistant.preferences.AppPreferenceState
import com.dax.assistant.preferences.AppPreferences
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ConversationsViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `loads list then binds selected backend session`() = runTest(dispatcher) {
        val summary = ConversationSummary("c1", "session-1", "Title", "Preview", "now", 2)
        val api = mockk<ConversationApi>()
        coEvery { api.list() } returns ConversationApiResult.Success(listOf(summary))
        coEvery { api.get("c1") } returns ConversationApiResult.Success(
            ConversationDetail(
                "c1",
                "session-1",
                "then",
                "now",
                listOf(ConversationMessage("m1", "user", "Hello", "now")),
            ),
        )
        val chat = MutableStateFlow(ConversationChatState("session-1"))
        val repository = mockk<ChatRepository> {
            every { connection } returns MutableStateFlow(ConnectionState.Connected)
            every { retain("session-1", any()) } returns chat
        }
        val viewModel = ConversationsViewModel(api, repository, mockk(relaxed = true), speakingPrefs())
        advanceUntilIdle()

        assertEquals(listOf(summary), viewModel.state.value.conversations)
        viewModel.select(summary)
        advanceUntilIdle()

        assertEquals("c1", viewModel.state.value.selectedConversationId)
        assertEquals("session-1", viewModel.state.value.chat?.sessionId)
        verify { repository.retain("session-1", match { it.single().content == "Hello" }) }
    }

    /** A typed conversation reads its answers aloud; a reopened one does not. */
    @Test
    fun `speaks a new assistant reply but never the history it opened with`() =
        runTest(dispatcher) {
            val chat = MutableStateFlow(
                ConversationChatState(
                    "session-1",
                    messages = listOf(ChatMessage("old", "assistant", "Said before", "then")),
                ),
            )
            val speaker = mockk<Speaker>(relaxed = true)
            val viewModel = boundViewModel(chat, speaker, speakingPrefs())
            advanceUntilIdle()

            // Opening the thread must stay silent — the user already read this.
            coVerify(exactly = 0) { speaker.speak(any()) }

            chat.value = chat.value.copy(
                messages = chat.value.messages + ChatMessage("new", "assistant", "Fresh answer", "now"),
            )
            advanceUntilIdle()

            coVerify(exactly = 1) { speaker.speak("Fresh answer") }
        }

    @Test
    fun `a reply still being written is not spoken until it is finished`() =
        runTest(dispatcher) {
            val chat = MutableStateFlow(ConversationChatState("session-1"))
            val speaker = mockk<Speaker>(relaxed = true)
            boundViewModel(chat, speaker, speakingPrefs())
            advanceUntilIdle()

            chat.value = chat.value.copy(
                messages = listOf(ChatMessage("m", "assistant", "Half a th", "now", pending = true)),
            )
            advanceUntilIdle()
            coVerify(exactly = 0) { speaker.speak(any()) }

            chat.value = chat.value.copy(
                messages = listOf(ChatMessage("m", "assistant", "Half a thought, finished", "now")),
            )
            advanceUntilIdle()
            coVerify(exactly = 1) { speaker.speak("Half a thought, finished") }
        }

    @Test
    fun `turning the setting off leaves the phone silent`() = runTest(dispatcher) {
        val chat = MutableStateFlow(ConversationChatState("session-1"))
        val speaker = mockk<Speaker>(relaxed = true)
        boundViewModel(chat, speaker, speakingPrefs(enabled = false))
        advanceUntilIdle()

        chat.value = chat.value.copy(
            messages = listOf(ChatMessage("new", "assistant", "Fresh answer", "now")),
        )
        advanceUntilIdle()

        coVerify(exactly = 0) { speaker.speak(any()) }
    }

    @Test
    fun `a second reply cuts the first one off rather than overlapping it`() =
        runTest(dispatcher) {
            val chat = MutableStateFlow(ConversationChatState("session-1"))
            val speaker = mockk<Speaker>(relaxed = true)
            boundViewModel(chat, speaker, speakingPrefs())
            advanceUntilIdle()

            chat.value = chat.value.copy(
                messages = listOf(ChatMessage("a", "assistant", "First", "now")),
            )
            advanceUntilIdle()
            chat.value = chat.value.copy(
                messages = chat.value.messages + ChatMessage("b", "assistant", "Second", "now"),
            )
            advanceUntilIdle()

            verify(atLeast = 1) { speaker.stop() }
            coVerify(exactly = 1) { speaker.speak("Second") }
        }

    private fun boundViewModel(
        chat: MutableStateFlow<ConversationChatState>,
        speaker: Speaker,
        preferences: AppPreferences,
    ): ConversationsViewModel {
        val api = mockk<ConversationApi>()
        coEvery { api.list() } returns ConversationApiResult.Success(emptyList())
        coEvery { api.get(any()) } returns ConversationApiResult.Success(
            ConversationDetail(
                "c1",
                "session-1",
                "then",
                "now",
                chat.value.messages.map {
                    ConversationMessage(it.id, it.role, it.content, it.timestamp)
                },
            ),
        )
        val repository = mockk<ChatRepository>(relaxed = true) {
            every { connection } returns MutableStateFlow(ConnectionState.Connected)
            every { retain("session-1", any()) } returns chat
        }
        val viewModel = ConversationsViewModel(api, repository, speaker, preferences)
        viewModel.select(ConversationSummary("c1", "session-1", "T", "P", "now", 1))
        return viewModel
    }

    private fun speakingPrefs(enabled: Boolean = true) = mockk<AppPreferences> {
        every { state } returns MutableStateFlow(AppPreferenceState(speakChatReplies = enabled))
    }
}
