package com.dax.assistant.ui.setup

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PairingPayloadTest {
    @Test
    fun validatesPairingCodeLocally() {
        assertTrue(isValidPairingCode("AB12CD34"))
        assertFalse(isValidPairingCode("short"))
        assertFalse(isValidPairingCode("AB12-CD3"))
    }
    @Test
    fun `parses encoded dax pairing uri`() {
        val payload = PairingPayload.parse(
            "dax://pair?url=https%3A%2F%2Fdax.example%3A8420&code=ab12cd34",
        )

        assertEquals("https://dax.example:8420", payload?.backendUrl)
        assertEquals("AB12CD34", payload?.code)
        assertEquals(PairingKind.CLIENT, payload?.kind)
    }

    @Test
    fun `parses a capability node pairing uri`() {
        val payload = PairingPayload.parse(
            "dax://pair?url=https%3A%2F%2Fdax.example&code=NODE1234&kind=capability_node",
        )

        assertEquals(PairingKind.CAPABILITY_NODE, payload?.kind)
    }

    @Test
    fun `rejects other schemes and incomplete payloads`() {
        assertNull(PairingPayload.parse("https://pair?url=https://dax.example&code=ABC"))
        assertNull(PairingPayload.parse("dax://pair?url=https://dax.example"))
    }
}
