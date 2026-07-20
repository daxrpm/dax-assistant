package com.dax.assistant.audio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SpeechEndpointDetectorTest {
    @Test
    fun `silence cannot endpoint before speech and eventually times out`() {
        val detector = SpeechEndpointDetector(noSpeechTimeoutMillis = 1_000)

        repeat(9) {
            assertEquals(EndpointDecision.CONTINUE, detector.accept(1_600, 100))
        }
        assertFalse(detector.speechDetected)
        assertEquals(EndpointDecision.NO_SPEECH_TIMEOUT, detector.accept(1_600, 100))
    }

    @Test
    fun `speech ends after nine hundred milliseconds of trailing silence`() {
        val detector = SpeechEndpointDetector()

        assertEquals(EndpointDecision.SPEECH_STARTED, detector.accept(1_600, 2_000))
        assertTrue(detector.speechDetected)
        repeat(8) {
            assertEquals(EndpointDecision.CONTINUE, detector.accept(1_600, 100))
        }
        assertEquals(EndpointDecision.END_OF_SPEECH, detector.accept(1_600, 100))
    }

    @Test
    fun `continuous speech is bounded to thirty seconds`() {
        val detector = SpeechEndpointDetector()

        assertEquals(EndpointDecision.SPEECH_STARTED, detector.accept(1_600, 2_000))
        repeat(298) { assertEquals(EndpointDecision.CONTINUE, detector.accept(1_600, 2_000)) }
        assertEquals(EndpointDecision.DURATION_LIMIT, detector.accept(1_600, 2_000))
    }

    @Test
    fun `rms measures pcm amplitude`() {
        assertEquals(1_000, SpeechEndpointDetector.rms(shortArrayOf(1_000, -1_000), 2))
    }
}
