package com.dax.assistant.core.log

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Redaction is the last line of defence before logcat, which any app holding
 * READ_LOGS can read. Each case here is a shape a credential actually arrives
 * in somewhere in this app.
 */
class DaxLogTest {

    @Test
    fun `masks the device secret in an enrolment response`() {
        val body = """{"ok":true,"device_id":"abc","device_secret":"s3cr3t-value-here"}"""

        val redacted = DaxLog.redact(body)

        assertFalse(redacted.contains("s3cr3t-value-here"))
        assertTrue(redacted.contains("\"device_secret\":\"***\""))
        // Non-sensitive fields must survive, or the log stops being useful.
        assertTrue(redacted.contains("\"device_id\":\"abc\""))
    }

    @Test
    fun `masks an access token in a token response`() {
        val body = """{"ok":true,"token":"eyJhbGciOi.payload.sig","expires_in_seconds":900}"""

        val redacted = DaxLog.redact(body)

        assertFalse(redacted.contains("eyJhbGciOi.payload.sig"))
        assertTrue(redacted.contains("expires_in_seconds"))
    }

    @Test
    fun `masks a bearer header wherever it appears`() {
        val message = "request failed: Authorization: Bearer abc.def-123_XYZ returned 401"

        val redacted = DaxLog.redact(message)

        assertFalse(redacted.contains("abc.def-123_XYZ"))
        assertTrue(redacted.contains("Bearer ***"))
        assertTrue(redacted.contains("returned 401"))
    }

    @Test
    fun `masks the token query parameter used on websocket urls`() {
        val url = "wss://dax.example/ws/voice?token=abc123XYZ.-_&session=s1"

        val redacted = DaxLog.redact(url)

        assertFalse(redacted.contains("abc123XYZ"))
        assertTrue(redacted.contains("token=***"))
        // The next parameter must not be swallowed by a greedy match.
        assertTrue(redacted.contains("session=s1"))
    }

    @Test
    fun `masks a pairing code`() {
        val redacted = DaxLog.redact("""{"code":"ABCD2345","name":"phone"}""")

        assertFalse(redacted.contains("ABCD2345"))
        assertTrue(redacted.contains("\"name\":\"phone\""))
    }

    @Test
    fun `masks a password field regardless of case`() {
        val redacted = DaxLog.redact("""{"Password":"hunter2"}""")

        assertFalse(redacted.contains("hunter2"))
    }

    @Test
    fun `masks every occurrence not just the first`() {
        val body = """{"token":"one","other":1,"secret":"two"}"""

        val redacted = DaxLog.redact(body)

        assertFalse(redacted.contains("one"))
        assertFalse(redacted.contains("two"))
    }

    @Test
    fun `leaves ordinary messages untouched`() {
        val message = "SCO route opened to Redmi Watch 5 Lite in 340ms"

        assertEquals(message, DaxLog.redact(message))
    }

    @Test
    fun `describes speech by length rather than content`() {
        val described = DaxLog.describeSpeech("apaga la luz del salon")

        assertFalse(described.contains("apaga"))
        assertFalse(described.contains("luz"))
    }

    @Test
    fun `describes absent speech without crashing`() {
        assertEquals("none", DaxLog.describeSpeech(null))
    }
}
