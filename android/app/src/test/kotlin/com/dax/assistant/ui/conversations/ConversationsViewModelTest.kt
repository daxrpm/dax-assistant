package com.dax.assistant.ui.conversations

import com.dax.assistant.data.conversations.ChatRepository
import com.dax.assistant.data.conversations.ConversationApi
import com.dax.assistant.data.conversations.ConversationApiResult
import com.dax.assistant.data.conversations.ConversationChatState
import com.dax.assistant.data.conversations.ConversationDetail
import com.dax.assistant.data.conversations.ConversationMessage
import com.dax.assistant.data.conversations.ConversationSummary
import com.dax.assistant.data.transport.ConnectionState
import io.mockk.coEvery
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
        val viewModel = ConversationsViewModel(api, repository)
        advanceUntilIdle()

        assertEquals(listOf(summary), viewModel.state.value.conversations)
        viewModel.select(summary)
        advanceUntilIdle()

        assertEquals("c1", viewModel.state.value.selectedConversationId)
        assertEquals("session-1", viewModel.state.value.chat?.sessionId)
        verify { repository.retain("session-1", match { it.single().content == "Hello" }) }
    }
}
