package com.dax.assistant.assistant

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AssistantControllerFollowUpTest {
    @Test
    fun `enabled preference arms one follow-up only after manual turn`() {
        assertTrue(shouldStartAutomaticFollowUp(completedAutomaticFollowUp = false, enabled = true))
        assertFalse(shouldStartAutomaticFollowUp(completedAutomaticFollowUp = true, enabled = true))
    }

    @Test
    fun `disabled preference never arms follow-up`() {
        assertFalse(shouldStartAutomaticFollowUp(completedAutomaticFollowUp = false, enabled = false))
    }
}
