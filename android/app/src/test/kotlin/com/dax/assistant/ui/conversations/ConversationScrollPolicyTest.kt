package com.dax.assistant.ui.conversations

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ConversationScrollPolicyTest {
    @Test
    fun emptyThreadIsNearEnd() {
        assertTrue(isNearConversationEnd(0, null))
    }

    @Test
    fun lastThreeItemsAreNearEnd() {
        assertTrue(isNearConversationEnd(20, 17))
        assertTrue(isNearConversationEnd(20, 19))
    }

    @Test
    fun olderViewportIsNotNearEnd() {
        assertFalse(isNearConversationEnd(20, 16))
    }
}
