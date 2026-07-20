package com.dax.assistant.ui.setup

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PairingPayloadTest {
    @Test
    fun `parses encoded dax pairing uri`() {
        val payload = PairingPayload.parse(
            "dax://pair?url=https%3A%2F%2Fdax.example%3A8420&code=ab12cd34",
        )

        assertEquals("https://dax.example:8420", payload?.backendUrl)
        assertEquals("AB12CD34", payload?.code)
    }

    @Test
    fun `rejects other schemes and incomplete payloads`() {
        assertNull(PairingPayload.parse("https://pair?url=https://dax.example&code=ABC"))
        assertNull(PairingPayload.parse("dax://pair?url=https://dax.example"))
    }
}
